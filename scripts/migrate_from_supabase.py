"""Copy core rows from a Supabase Postgres into the FastAPI DB.

Usage:
  PYTHONPATH=. uv run python scripts/migrate_from_supabase.py

Loads SUPABASE_DATABASE_URL + DATABASE_URL from .env.
Use the Session pooler URL if direct db.* host is IPv6-only.
ponytail: auth passwords are random — users must OTP-reset.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import sys
import uuid
from pathlib import Path

import asyncpg
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

TABLES = [
    "doctor_categories",
    "hospitals",
    "doctor_profiles",
    "profiles",
    "pregnancies",
    "pregnancy_logs",
    "pregnancy_weeks",
    "pregnancy_week_translations",
    "children",
    "child_growth_periods",
    "child_growth_period_translations",
    "child_growth_measurements",
    "child_milestone_checks",
    "child_vaccine_records",
    "vaccine_dose_schedule",
    "symptom_catalog",
    "daily_tips",
    "daily_tip_translations",
    "growth_clinical_advice",
    "growth_clinical_advice_translations",
    # symptom_catalog: source uses text ids; dest uses uuid — skip
    "doctor_services",
    "doctor_availability_slots",
    "appointments",
    "appointment_reviews",
    "chat_conversations",
    "chat_messages",
    "notifications",
    "app_settings",
    "legal_documents",
    "doctor_payout_methods",
    "doctor_payout_requests",
    "patient_wallets",
    "patient_wallet_transactions",
    "doctor_wallets",
    "wallet_transactions",
    "app_subscriptions",
    "care_subscriptions",
]


async def upsert_user(conn, *, user_id, phone: str, role: str, password_hash: str) -> None:
    phone = phone[:32]
    by_id = (
        await conn.execute(text("select id, phone, roles from users where id = :id"), {"id": user_id})
    ).mappings().first()
    if by_id is not None:
        roles = list(by_id["roles"] or [])
        if role not in roles:
            roles.append(role)
            await conn.execute(text("update users set roles = :roles where id = :id"), {"roles": roles, "id": user_id})
        return

    by_phone = (
        await conn.execute(text("select id, roles from users where phone = :phone"), {"phone": phone})
    ).mappings().first()
    if by_phone is not None:
        phone = f"{phone[:20]}+{role[0]}{str(user_id)[:8]}"[:32]
        print(f"warn: phone clash for {role} {user_id}; storing as {phone}")

    await conn.execute(
        text(
            "insert into users (id, phone, password_hash, role, roles, is_active) "
            "values (:id, :phone, :ph, :role, :roles, true)"
        ),
        {"id": user_id, "phone": phone, "ph": password_hash, "role": role, "roles": [role]},
    )


async def copy_table(conn, src, table: str, dst_cols: dict[str, set[str]]) -> None:
    src_names = [table]
    if table == "vaccine_dose_schedule":
        src_names = ["vaccine_dose_schedule", "vaccine_dose_schedules"]
    rows = None
    last_exc: Exception | None = None
    for name in src_names:
        try:
            rows = await src.fetch(f"select * from {name}")
            break
        except Exception as exc:
            last_exc = exc
    if rows is None:
        print(f"skip {table}: {last_exc}")
        return
    if not rows:
        print(f"empty {table}")
        return
    if table not in dst_cols:
        res = await conn.execute(
            text(
                "select column_name from information_schema.columns "
                "where table_schema='public' and table_name=:t"
            ),
            {"t": table},
        )
        dst_cols[table] = {r[0] for r in res.fetchall()}
    if not dst_cols[table]:
        print(f"skip {table}: missing on destination")
        return
    cols = [c for c in rows[0].keys() if c in dst_cols[table]]
    if table == "legal_documents" and "id" in dst_cols[table] and "id" not in cols:
        cols = ["id", *cols]
    if not cols:
        print(f"skip {table}: no overlapping columns")
        return
    col_list = ", ".join(cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    stmt = text(f"insert into {table} ({col_list}) values ({placeholders}) on conflict do nothing")
    limits_res = await conn.execute(
        text(
            "select column_name, character_maximum_length from information_schema.columns "
            "where table_schema='public' and table_name=:t and character_maximum_length is not null"
        ),
        {"t": table},
    )
    limits = {r[0]: int(r[1]) for r in limits_res.fetchall()}
    async with conn.begin_nested():
        for r in rows:
            payload = {}
            for c in cols:
                if c == "id" and table == "legal_documents":
                    v = r.get("id") if hasattr(r, "get") else r["id"] if "id" in r.keys() else None
                    payload[c] = v or uuid.uuid4()
                    continue
                v = r[c]
                if table == "symptom_catalog" and c == "id" and not isinstance(v, uuid.UUID):
                    v = uuid.uuid5(uuid.NAMESPACE_URL, f"icare-symptom:{v}")
                lim = limits.get(c)
                if isinstance(v, str) and lim is not None and len(v) > lim:
                    v = v[:lim]
                payload[c] = v
            await conn.execute(stmt, payload)
    print(f"copied {table}: {len(rows)}")


async def main() -> None:
    src_url = os.environ.get("SUPABASE_DATABASE_URL")
    dst_url = os.environ.get("DATABASE_URL")
    if not src_url or not dst_url:
        print("Set SUPABASE_DATABASE_URL and DATABASE_URL", file=sys.stderr)
        sys.exit(1)

    src = await asyncpg.connect(src_url, timeout=60, ssl="require")
    engine = create_async_engine(dst_url)

    from app.core.security.tokens import hash_password

    async with engine.begin() as conn:
        for row in await src.fetch("select id, phone from profiles"):
            phone = (row["phone"] or f"m-{str(row['id'])[:12]}")[:32]
            await upsert_user(
                conn,
                user_id=row["id"],
                phone=phone,
                role="patient",
                password_hash=hash_password(secrets.token_urlsafe(24)),
            )
        for row in await src.fetch("select id, phone from doctor_profiles"):
            phone = (row["phone"] or f"d-{str(row['id'])[:12]}")[:32]
            await upsert_user(
                conn,
                user_id=row["id"],
                phone=phone,
                role="doctor",
                password_hash=hash_password(secrets.token_urlsafe(24)),
            )

        dst_cols: dict[str, set[str]] = {}
        for table in TABLES:
            try:
                await copy_table(conn, src, table, dst_cols)
            except Exception as exc:
                print(f"skip {table}: {exc}")

    await src.close()
    await engine.dispose()
    print("done — users must reset passwords via OTP")


if __name__ == "__main__":
    asyncio.run(main())
