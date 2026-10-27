"""Chat photo / voice attachment storage helpers."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import MySettings

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
ALLOWED_AUDIO_TYPES = {
    "audio/mp4": "m4a",
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
    "audio/aac": "aac",
    "audio/mpeg": "mp3",
}
ALLOWED_CONTENT_TYPES = {**ALLOWED_IMAGE_TYPES, **ALLOWED_AUDIO_TYPES}

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB


def media_root() -> Path:
    root = Path(MySettings.MEDIA_ROOT)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[3] / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def public_url_for(file_path: str | None) -> str | None:
    if not file_path:
        return None
    raw = file_path.strip()
    if not raw:
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    prefix = MySettings.MEDIA_URL_PREFIX.rstrip("/")
    if raw.startswith("/"):
        return raw if raw.startswith(prefix) else f"{prefix}{raw}"
    return f"{prefix}/{raw}"


def message_row(obj) -> dict:
    data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    data["url"] = public_url_for(getattr(obj, "file_path", None))
    return data


def _ext_for(content_type: str, filename: str | None) -> str:
    mapped = ALLOWED_CONTENT_TYPES.get(content_type)
    if mapped:
        return mapped
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in {"jpg", "jpeg", "png", "webp", "m4a", "aac", "mp3"}:
            return "jpg" if ext == "jpeg" else ext
    raise HTTPException(status_code=400, detail="Unsupported file type.")


async def save_chat_attachment(
    *,
    conversation_id: uuid.UUID,
    upload: UploadFile,
) -> dict[str, str]:
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="File type not allowed. Use JPEG/PNG/WebP images or M4A/AAC audio.",
        )

    data = await upload.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 10MB).")

    ext = _ext_for(content_type, upload.filename)
    relative = f"chat/{conversation_id}/{uuid.uuid4().hex}.{ext}"
    dest = media_root() / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)

    return {
        "file_path": relative.replace("\\", "/"),
        "url": public_url_for(relative) or f"/static/{relative}",
        "content_type": content_type,
    }


def validate_attachment_for_message(
    *,
    conversation_id: uuid.UUID,
    message_type: str,
    file_path: str | None,
    duration_ms: int | None,
) -> None:
    if message_type == "text":
        if file_path:
            raise HTTPException(status_code=400, detail="Text messages cannot include a file.")
        return

    if message_type not in {"image", "voice"}:
        raise HTTPException(status_code=400, detail="Invalid message_type.")
    if not file_path or not file_path.strip():
        raise HTTPException(status_code=400, detail="file_path is required for media messages.")

    path = file_path.strip().replace("\\", "/")
    expected_prefix = f"chat/{conversation_id}/"
    if not path.startswith(expected_prefix):
        raise HTTPException(status_code=400, detail="file_path does not belong to this conversation.")
    if ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="Invalid file_path.")

    full = media_root() / path
    if not full.is_file():
        raise HTTPException(status_code=400, detail="Attachment file not found. Upload first.")

    if message_type == "voice" and (duration_ms is None or duration_ms < 0):
        raise HTTPException(status_code=400, detail="duration_ms is required for voice messages.")
