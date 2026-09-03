from uuid import UUID

from pydantic import BaseModel, Field


class PushIn(BaseModel):
    user_id: UUID
    title: str
    body: str
    type: str = "generic"
    data: dict[str, object] = Field(default_factory=dict)
