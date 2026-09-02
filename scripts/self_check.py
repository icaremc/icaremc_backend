"""Minimal import/self-check: python -m scripts.self_check"""

from fastapi.testclient import TestClient

from app.persistence.sqlalchemy.base import Base
import app.persistence.sqlalchemy.models  # noqa: F401
from app.api import create_app


def main() -> None:
    assert "users" in Base.metadata.tables
    assert "appointments" in Base.metadata.tables
    assert "child_followup_visits" in Base.metadata.tables
    assert "otp_challenges" in Base.metadata.tables
    app = create_app()
    client = TestClient(app)
    assert client.get("/api/v1/health").status_code == 200
    print("ok", len(Base.metadata.tables), "tables")


if __name__ == "__main__":
    main()
