from pydantic import BaseModel

class SendSmsIn(BaseModel):
    phone: str
    message: str

class SendBulkSmsIn(BaseModel):
    phones: list[str]
    message: str

class SendSmsOut(BaseModel):
    status: str
