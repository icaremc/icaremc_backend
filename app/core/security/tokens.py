import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.config import MySettings

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def create_access_token(*, sub: UUID, role: str, extra: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {
        "sub": str(sub),
        "role": role,
        "exp": datetime.now(UTC) + timedelta(minutes=MySettings.JWT_ACCESS_EXPIRE_MINUTES),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, MySettings.JWT_SECRET, algorithm=MySettings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, MySettings.JWT_SECRET, algorithms=[MySettings.JWT_ALGORITHM])


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
