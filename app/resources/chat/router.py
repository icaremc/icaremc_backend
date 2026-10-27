from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.v1.schemas import RowOut
from app.core.security.deps import RequirePatient
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.chat.repository import SqlAlchemyChatRepository
from app.resources.chat.schemas import AttachmentOut, ChatIn
from app.resources.chat.service import ChatService

router = APIRouter(tags=["mother"])


def get_chat_service(db: DbDep) -> ChatService:
    return ChatService(SqlAlchemyChatRepository(db))


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


@router.get("/chat/conversations")
async def chat_conversations(user: RequirePatient, svc: ChatServiceDep) -> list[RowOut]:
    return await svc.list_patient(user.id)


@router.get("/chat/conversations/{conversation_id}/messages")
async def chat_messages(conversation_id: UUID, user: RequirePatient, svc: ChatServiceDep) -> list[RowOut]:
    return await svc.messages_patient(conversation_id, user.id)


@router.post("/chat/conversations/{conversation_id}/attachments")
async def upload_chat_attachment(
    conversation_id: UUID,
    user: RequirePatient,
    svc: ChatServiceDep,
    file: UploadFile = File(...),
) -> AttachmentOut:
    return await svc.upload_patient(conversation_id, user.id, file)


@router.post("/chat/conversations/{conversation_id}/messages")
async def send_chat(conversation_id: UUID, body: ChatIn, user: RequirePatient, svc: ChatServiceDep) -> RowOut:
    return await svc.send_patient(conversation_id, user.id, body)


@router.post("/chat/conversations/{conversation_id}/read")
@router.post("/chat/conversations/{conversation_id}/seen")
async def mark_chat_seen(conversation_id: UUID, user: RequirePatient, svc: ChatServiceDep) -> dict[str, object]:
    return await svc.mark_read_patient(conversation_id, user.id)
