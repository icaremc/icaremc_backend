from datetime import UTC, datetime
from uuid import UUID

from app.api.v1.schemas import RowOut
from app.persistence.sqlalchemy.models import ChatMessage
from app.resources.chat.repository import ChatRepository
from app.resources.chat.schemas import ChatIn
from app.resources.errors import not_found
from app.resources.push.fcm import send_fcm
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

        # Real-time push notification to the doctor
        sender_name = "Patient"
        if hasattr(self._repo, "get_profile"):
            p = await self._repo.get_profile(user_id)
            if p and p.full_name:
                sender_name = p.full_name

        doctor = await self._repo.get_doctor(conv.doctor_id) if hasattr(self._repo, "get_doctor") else None
        if doctor and doctor.fcm_token and doctor.notifications_enabled is not False:
            title = f"New message from {sender_name}"
            preview = text[:100] + ("..." if len(text) > 100 else "")
            chat_data = {
                "type": "chat",
                "screen": "doctor_chat_room",
                "route": f"/doctor/messages/{conversation_id}",
                "conversation_id": str(conversation_id),
                "sender_id": str(user_id),
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
            }
            await send_fcm(doctor.fcm_token, title, preview, chat_data)

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

        # Real-time push notification to the patient
        doc_name = "Your Doctor"
        if hasattr(self._repo, "get_doctor"):
            d = await self._repo.get_doctor(user_id)
            if d:
                names = f"{getattr(d, 'first_name', '') or ''} {getattr(d, 'last_name', '') or ''}".strip()
                if names:
                    doc_name = names if names.lower().startswith("dr.") else f"Dr. {names}"

        patient = await self._repo.get_profile(conv.patient_id) if hasattr(self._repo, "get_profile") else None
        if patient and patient.fcm_token and patient.notifications_enabled is not False:
            title = doc_name
            preview = text[:100] + ("..." if len(text) > 100 else "")
            chat_data = {
                "type": "chat",
                "screen": "patient_chat_room",
                "route": f"/messages/{conversation_id}",
                "conversation_id": str(conversation_id),
                "sender_id": str(user_id),
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
            }
            await send_fcm(patient.fcm_token, title, preview, chat_data)

        await self._repo.flush()
        return require_row(msg)
