import mimetypes
import os
import shutil
import uuid
from fastapi import UploadFile

ALLOWED_EXTENSIONS = {
    # Images
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico", ".heic", ".heif", ".tiff", ".tif",
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".rtf", ".json",
    # Audio
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".weba", ".flac",
    # Video
    ".mp4", ".mov", ".webm", ".mkv", ".avi",
}

DISALLOWED_EXTENSIONS = {
    ".exe", ".dll", ".so", ".sh", ".bat", ".cmd", ".bin", ".msi",
    ".php", ".phtml", ".php3", ".php4", ".php5", ".phps",
    ".py", ".pyc", ".pyo", ".js", ".mjs", ".cgi", ".pl",
    ".jsp", ".asp", ".aspx", ".jar", ".vbs", ".wsf", ".scr",
}

ALLOWED_MIME_PREFIXES = ("image/", "audio/", "video/")

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/csv",
    "application/rtf",
    "application/json",
}


def is_allowed_file(filename: str | None, content_type: str | None) -> bool:
    raw_name = filename or ""
    ext = os.path.splitext(raw_name)[1].lower()

    if ext in DISALLOWED_EXTENSIONS:
        return False

    if ext in ALLOWED_EXTENSIONS:
        return True

    guessed_type, _ = mimetypes.guess_type(raw_name)
    effective_type = content_type or guessed_type or ""

    if effective_type.startswith(ALLOWED_MIME_PREFIXES):
        return True

    if effective_type in ALLOWED_MIME_TYPES:
        return True

    return False


class UploadService:
    def __init__(self):
        self.upload_dir = "static/uploads"
        os.makedirs(self.upload_dir, exist_ok=True)
        self.base_url = os.environ.get("BASE_URL", "")

    def upload_file(self, file: UploadFile) -> dict[str, object]:
        """
        Uploads an image or document to the local filesystem and returns its URL and metadata.
        """
        raw_name = file.filename or "upload"
        _, raw_ext = os.path.splitext(raw_name)
        # Keep only alphanumeric chars in extension for safety
        ext = "".join(c for c in raw_ext.lower() if c.isalnum() or c == ".")

        unique_filename = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(self.upload_dir, unique_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        size = os.path.getsize(file_path)

        guessed_type, _ = mimetypes.guess_type(raw_name)
        mime_type = file.content_type or guessed_type or "application/octet-stream"

        if self.base_url:
            endpoint = self.base_url.rstrip("/")
            url = f"{endpoint}/{self.upload_dir}/{unique_filename}"
        else:
            url = f"/{self.upload_dir}/{unique_filename}"

        return {
            "url": url,
            "file_name": raw_name,
            "mime_type": mime_type,
            "size": size,
        }

    def upload_image(self, file: UploadFile) -> str:
        """
        Backward-compatible helper that returns only the URL string.
        """
        result = self.upload_file(file)
        return str(result["url"])

