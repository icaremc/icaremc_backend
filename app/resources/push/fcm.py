import asyncio
import logging
from typing import Any
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, messaging

from app.config import MySettings

logger = logging.getLogger(__name__)

_firebase_app: firebase_admin.App | None = None


def _build_service_account_dict() -> dict[str, str] | None:
    project_id = MySettings.FIREBASE_PROJECT_ID or MySettings.FCM_PROJECT_ID
    private_key = MySettings.FIREBASE_PRIVATE_KEY
    client_email = MySettings.FIREBASE_CLIENT_EMAIL

    if not project_id or not private_key or not client_email:
        return None

    # Handle escaped newlines from .env (e.g. "\\n" -> "\n") and trim accidental quotes
    formatted_private_key = private_key.strip("'\"").replace("\\n", "\n")

    return {
        "type": "service_account",
        "project_id": project_id,
        "private_key_id": MySettings.FIREBASE_PRIVATE_KEY_ID,
        "private_key": formatted_private_key,
        "client_email": client_email,
        "client_id": MySettings.FIREBASE_CLIENT_ID,
        "auth_uri": MySettings.FIREBASE_AUTH_URI,
        "token_uri": MySettings.FIREBASE_TOKEN_URI,
        "auth_provider_x509_cert_url": MySettings.FIREBASE_AUTH_PROVIDER_X509_CERT_URL,
        "client_x509_cert_url": (
            MySettings.FIREBASE_CLIENT_X509_CERT_URL
            or f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email}"
        ),
        "universe_domain": MySettings.FIREBASE_UNIVERSE_DOMAIN,
    }


def get_firebase_app() -> firebase_admin.App | None:
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    if firebase_admin._apps:
        _firebase_app = firebase_admin.get_app()
        return _firebase_app

    cred_dict = _build_service_account_dict()
    cred = None

    if cred_dict:
        try:
            cred = credentials.Certificate(cred_dict)
        except Exception as exc:
            logger.error("Failed to initialize Firebase credentials from environment values: %s", exc)
            return None
    elif MySettings.FIREBASE_CREDENTIALS_PATH and Path(MySettings.FIREBASE_CREDENTIALS_PATH).exists():
        try:
            cred = credentials.Certificate(MySettings.FIREBASE_CREDENTIALS_PATH)
        except Exception as exc:
            logger.error("Failed to initialize Firebase credentials from file path: %s", exc)
            return None

    if cred is None:
        return None

    try:
        _firebase_app = firebase_admin.initialize_app(cred)
        return _firebase_app
    except Exception as exc:
        logger.error("Failed to initialize Firebase App: %s", exc)
        return None


async def send_fcm(
    token: str,
    title: str,
    body: str,
    data: dict[str, object] | None = None,
) -> dict[str, Any]:
    if not token:
        return {"ok": False, "skipped": True}

    app = get_firebase_app()
    if app is None:
        return {"ok": False, "skipped": True}

    str_data = {str(k): str(v) for k, v in (data or {}).items()}

    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=str_data,
        token=token,
    )

    try:
        message_id = await asyncio.to_thread(messaging.send, message, app=app)
        return {"ok": True, "message_id": message_id}
    except Exception as exc:
        logger.warning("FCM send failed: %s", exc)
        return {"ok": False, "error": str(exc)}
