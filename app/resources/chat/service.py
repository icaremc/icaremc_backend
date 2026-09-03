from datetime import UTC, datetime
from uuid import UUID

from app.api.v1.schemas import RowOut
from app.persistence.sqlalchemy.models import ChatMessage
from app.resources.chat.repository import ChatRepository
from app.resources.chat.schemas import ChatIn
from app.resources.errors import not_found
from app.resources.serialize import require_row, to_rows


class ChatService:
    def __init__(self, repo: ChatRepository) -> None:
        self._repo = repo

    async def list_patient(self, user_id: UUID) -> list[RowOut]:
        return to_rows(await self._repo.list_for_patient(user_id))

    async def list_doctor(self, user_id: UUID) -> list[RowOut]:
        return to_rows(await self._repo.list_for_doctor(user_id))

    async def messages_patient(self, conversation_id: UUID, user_id: UUID) -> list[RowOut]:
        conv = await self._repo.get_for_patient(conversation_id, user_id)
        if conv is None:
            raise not_found()
        return to_rows(await self._repo.list_messages(conversation_id))

    async def messages_doctor(self, conversation_id: UUID, user_id: UUID) -> list[RowOut]:
        conv = await self._repo.get_for_doctor(conversation_id, user_id)
        if conv is None:
            raise not_found()
        return to_rows(await self._repo.list_messages(conversation_id))

    async def send_patient(self, conversation_id: UUID, user_id: UUID, body: ChatIn) -> RowOut:
        conv = await self._repo.get_for_patient(conversation_id, user_id)
        if conv is None:
            raise not_found()
        text = body.body.strip()
        msg = ChatMessage(conversation_id=conversation_id, sender_id=user_id, body=text)
        self._repo.add(msg)
        conv.last_message = text
        conv.last_message_at = datetime.now(UTC)
        conv.doctor_unread_count += 1
        await self._repo.flush()
        return require_row(msg)

    async def send_doctor(self, conversation_id: UUID, user_id: UUID, body: ChatIn) -> RowOut:
        conv = await self._repo.get_for_doctor(conversation_id, user_id)
        if conv is None:
            raise not_found()
        text = body.body.strip()
        msg = ChatMessage(conversation_id=conversation_id, sender_id=user_id, body=text)
        self._repo.add(msg)
        conv.last_message = text
        conv.last_message_at = datetime.now(UTC)
        conv.patient_unread_count += 1
        await self._repo.flush()
        return require_row(msg)
