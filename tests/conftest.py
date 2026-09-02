import os
import subprocess
import uuid

# Must set before importing app modules
os.environ["DATABASE_URL"] = "postgresql+asyncpg://app_user:password@localhost:5432/app_db_test"
os.environ["JWT_SECRET"] = "test-jwt-secret-at-least-32-bytes!!"
os.environ["ENVIRONMENT"] = "1"
os.environ["SMS_OTP_DEV_CODE"] = "123456"
os.environ["SMS_API_BASE_URL"] = ""
os.environ["CHAPA_SECRET_KEY"] = ""
os.environ["FCM_SERVER_KEY"] = ""

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api import create_app
from app.persistence.sqlalchemy.base import Base
import app.persistence.sqlalchemy.connection as connection
import app.persistence.sqlalchemy.models  # noqa: F401

# Fresh NullPool engine so TestClient / asyncio.run don't fight pooled connections
connection.async_engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
connection.async_session_factory = async_sessionmaker(
    connection.async_engine, autoflush=False, expire_on_commit=False
)
async_engine = connection.async_engine

_PSQL = [
    "psql",
    "-h",
    "localhost",
    "-U",
    "app_user",
    "-d",
    "app_db_test",
    "-v",
    "ON_ERROR_STOP=1",
]
_PSQL_ENV = {**os.environ, "PGPASSWORD": "password"}


def _psql(sql: str) -> None:
    subprocess.run([*_PSQL, "-c", sql], check=True, env=_PSQL_ENV, capture_output=True, text=True)


def _reset_schema() -> None:
    _psql("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO CURRENT_USER; GRANT ALL ON SCHEMA public TO public;")

    async def _create() -> None:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create())


def _truncate_all() -> None:
    _psql(
        "DO $$ DECLARE r RECORD; BEGIN "
        "FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP "
        "EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE'; "
        "END LOOP; END $$;"
    )


@pytest.fixture(scope="session")
def app():
    _reset_schema()
    application = create_app()
    yield application
    asyncio.run(async_engine.dispose())


@pytest.fixture
def client(app):
    _truncate_all()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def unique_phone():
    def _make(prefix: str = "9") -> str:
        suffix = uuid.uuid4().hex[:8]
        return f"0{prefix}{suffix}"

    return _make


@pytest.fixture
def patient_auth(client, unique_phone):
    phone = unique_phone("91")
    otp = client.post("/api/v1/auth/patient/otp", json={"phone": phone}).json()
    assert otp["ok"] is True
    signup = client.post(
        "/api/v1/auth/patient/signup",
        json={
            "phone": phone,
            "password": "secret12",
            "otp": otp["dev_code"],
            "full_name": "Test Mother",
        },
    )
    assert signup.status_code == 200, signup.text
    body = signup.json()
    return {"token": body["access_token"], "user_id": body["user_id"], "phone": phone}


@pytest.fixture
def doctor_auth(client, unique_phone):
    phone = unique_phone("92")
    otp = client.post("/api/v1/auth/doctor/otp", json={"phone": phone}).json()
    assert otp["ok"] is True
    signup = client.post(
        "/api/v1/auth/doctor/signup",
        json={
            "phone": phone,
            "password": "secret12",
            "otp": otp["dev_code"],
            "first_name": "Doc",
            "last_name": "Tor",
            "specialty": "OBGYN",
        },
    )
    assert signup.status_code == 200, signup.text
    body = signup.json()
    return {"token": body["access_token"], "user_id": body["user_id"], "phone": phone}


@pytest.fixture
def admin_auth(client):
    boot = client.post(
        "/api/v1/admin/bootstrap-super-admin",
        json={
            "email": "admin@test.icaremc.app",
            "password": "adminpass123",
            "full_name": "Test Admin",
        },
    )
    assert boot.status_code == 200, boot.text
    login = client.post(
        "/api/v1/auth/admin/login",
        json={"email": "admin@test.icaremc.app", "password": "adminpass123"},
    )
    assert login.status_code == 200, login.text
    body = login.json()
    return {"token": body["access_token"], "user_id": body["user_id"]}


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
