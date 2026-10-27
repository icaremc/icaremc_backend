from uuid import UUID

from pydantic import BaseModel, Field


class StartVideoCallIn(BaseModel):
    conversation_id: UUID


class VideoCallJoinOut(BaseModel):
    id: UUID
    conversation_id: UUID
    appointment_id: UUID
    channel_name: str
    app_id: str
    token: str
    uid: int
    status: str
    started_at: str
    ends_at: str
    remaining_seconds: int
    warn_seconds: int = 120
    role: str


class VideoCallStatusOut(BaseModel):
    id: UUID
    conversation_id: UUID
    appointment_id: UUID
    channel_name: str
    status: str
    started_at: str
    ends_at: str
    remaining_seconds: int
    warn_seconds: int = 120


class EndVideoCallOut(BaseModel):
    ok: bool = True
    id: UUID
    status: str = Field(default="ended")
