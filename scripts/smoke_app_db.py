"""Read-only smoke checks against local app_db (migrated data). Does not truncate.

  PYTHONPATH=. uv run python scripts/smoke_app_db.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# Ensure we use app_db from .env, not a test override
os.environ.pop("SMS_OTP_DEV_CODE", None)


def main() -> int:
    db_url = os.environ.get("DATABASE_URL", "")
    if "app_db_test" in db_url:
        print("DATABASE_URL points at app_db_test — refuse to smoke-test wipe DB as app_db", file=sys.stderr)
        return 1
    if not db_url:
        print("Set DATABASE_URL", file=sys.stderr)
        return 1

    import app.persistence.sqlalchemy.connection as connection
    import app.persistence.sqlalchemy.models  # noqa: F401
    from app.api import create_app

    engine = create_async_engine(db_url, poolclass=NullPool)
    connection.async_engine = engine
    connection.async_session_factory = async_sessionmaker(engine, autoflush=False, expire_on_commit=False)

    async def counts() -> dict[str, int]:
        out: dict[str, int] = {}
        async with engine.connect() as conn:
            for t in (
                "users",
                "profiles",
                "doctor_profiles",
                "pregnancy_weeks",
                "pregnancy_week_translations",
                "children",
                "appointments",
                "legal_documents",
            ):
                out[t] = int((await conn.execute(text(f"select count(*) from {t}"))).scalar_one())
        return out

    row_counts = asyncio.run(counts())
    print("counts:", row_counts)
    failed = False
    for key in ("users", "profiles", "pregnancy_weeks", "legal_documents"):
        if row_counts.get(key, 0) < 1:
            print(f"FAIL: expected {key} > 0")
            failed = True

    app = create_app()
    with TestClient(app) as client:
        checks = [
            ("GET", "/api/v1/health", None, 200),
            ("GET", "/api/v1/cms/pregnancy-weeks", None, 200),
            ("GET", "/api/v1/cms/pregnancy-weeks?lang=am", None, 200),
            ("GET", "/api/v1/cms/child-growth-periods", None, 200),
            ("GET", "/api/v1/cms/daily-tips", None, 200),
            ("GET", "/api/v1/cms/legal/privacy-policy", None, 200),
            ("GET", "/api/v1/doctors", None, 200),
            ("GET", "/api/v1/doctors/categories", None, 200),
        ]
        for method, path, body, expect in checks:
            resp = client.request(method, path, json=body)
            ok = resp.status_code == expect
            print(f"{'OK' if ok else 'FAIL'} {method} {path} -> {resp.status_code}")
            if not ok:
                failed = True
                print(resp.text[:300])
            if path.startswith("/api/v1/cms/pregnancy-weeks") and resp.status_code == 200:
                data = resp.json()
                if not data:
                    print("FAIL: pregnancy-weeks empty")
                    failed = True
                elif data[0].get("translation") is None and "?lang=" not in path:
                    print("WARN: week has no translation")

    asyncio.run(engine.dispose())
    if failed:
        print("smoke FAILED")
        return 1
    print("smoke OK — app_db untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
