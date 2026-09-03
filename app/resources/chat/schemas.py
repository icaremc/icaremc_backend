from pydantic import BaseModel, Field


class ChatIn(BaseModel):
    body: str = Field(min_length=1)
