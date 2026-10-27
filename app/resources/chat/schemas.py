from pydantic import BaseModel, Field


class ChatIn(BaseModel):
    body: str = ""
    message_type: str = "text"
    file_path: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class AttachmentOut(BaseModel):
    file_path: str
    url: str
    content_type: str
