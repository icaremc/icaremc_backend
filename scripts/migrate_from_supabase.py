"""Copy core rows from a Supabase Postgres into the FastAPI DB.

Usage:
  SUPABASE_DATABASE_URL=postgresql://... DATABASE_URL=postgresql+asyncpg://... \
    python scripts/migrate_from_supabase.py

ponytail: copies public domain tables; auth users get random passwords (OTP reset required).
"""

from __future__ import annotations

import asyncio
import os
import secrets
import sys

import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

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
    "doctor_services",
    "doctor_availability_slots",
    "appointments",
    "chat_conversations",
    "chat_messages",
    "notifications",
    "app_settings",
    "legal_documents",
]


async def main() -> None:
    src_url = os.environ.get("SUPABASE_DATABASE_URL")
    dst_url = os.environ.get("DATABASE_URL")
    if not src_url or not dst_url:
        print("Set SUPABASE_DATABASE_URL and DATABASE_URL", file=sys.stderr)
        sys.exit(1)

    src = await asyncpg.connect(src_url)
    engine = create_async_engine(dst_url)

    from app.core.security.tokens import hash_password

    async with engine.begin() as conn:
        # users from profiles / doctor_profiles ids
        profile_ids = await src.fetch("select id, phone from profiles")
        for row in profile_ids:
            phone = row["phone"] or f"migrated-{row['id']}"
            await conn.execute(
                text(
                    "insert into users (id, phone, password_hash, role, is_active) "
                    "values (:id, :phone, :ph, 'patient', true) on conflict (id) do nothing"
                ),
                {"id": row["id"], "phone": phone, "ph": hash_password(secrets.token_urlsafe(24))},
            )
        doctor_ids = await src.fetch("select id, phone from doctor_profiles")
        for row in doctor_ids:
            phone = row["phone"] or f"doctor-{row['id']}"
            await conn.execute(
                text(
                    "insert into users (id, phone, password_hash, role, is_active) "
                    "values (:id, :phone, :ph, 'doctor', true) on conflict (id) do nothing"
                ),
                {"id": row["id"], "phone": phone, "ph": hash_password(secrets.token_urlsafe(24))},
            )

        for table in TABLES:
            try:
                rows = await src.fetch(f"select * from {table}")
            except Exception as exc:
                print(f"skip {table}: {exc}")
                continue
            if not rows:
                continue
            cols = list(rows[0].keys())
            col_list = ", ".join(cols)
            placeholders = ", ".join(f":{c}" for c in cols)
            stmt = text(
                f"insert into {table} ({col_list}) values ({placeholders}) on conflict do nothing"
            )
            for r in rows:
                await conn.execute(stmt, dict(r))
            print(f"copied {table}: {len(rows)}")

    await src.close()
    await engine.dispose()
    print("done — users must reset passwords via OTP")


if __name__ == "__main__":
    asyncio.run(main())
