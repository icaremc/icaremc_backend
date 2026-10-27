from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import UploadFile

from app.core.services.chat_attachments import (
    message_row,
    save_chat_attachment,
    validate_attachment_for_message,
)
from app.persistence.sqlalchemy.models import ChatMessage
from app.resources.chat.repository import ChatRepository
from app.resources.chat.schemas import AttachmentOut, ChatIn
from app.resources.errors import bad_request, not_found
from app.resources.push.fcm import send_fcm

if TYPE_CHECKING:
    from app.api.v1.schemas import RowOut


def _message_out(msg: ChatMessage) -> RowOut:
    from app.api.v1.schemas import RowOut

    return RowOut.model_validate(message_row(msg))


class ChatService:
    def __init__(self, repo: ChatRepository) -> None:
        self._repo = repo

    async def list_patient(self, user_id: UUID) -> list[RowOut]:
        from app.resources.serialize import to_rows

        return to_rows(await self._repo.list_for_patient(user_id))

    async def list_doctor(self, user_id: UUID) -> list[RowOut]:
        from app.resources.serialize import to_rows

        return to_rows(await self._repo.list_for_doctor(user_id))

    async def messages_patient(self, conversation_id: UUID, user_id: UUID) -> list[RowOut]:
        conv = await self._repo.get_for_patient(conversation_id, user_id)
        if conv is None:
            raise not_found()
        if hasattr(self._repo, "mark_messages_seen"):
            await self._repo.mark_messages_seen(conversation_id, exclude_sender_id=user_id)
            conv.patient_unread_count = 0
            await self._repo.flush()
        return [_message_out(m) for m in await self._repo.list_messages(conversation_id)]

    async def messages_doctor(self, conversation_id: UUID, user_id: UUID) -> list[RowOut]:
        conv = await self._repo.get_for_doctor(conversation_id, user_id)
        if conv is None:
            raise not_found()
        if hasattr(self._repo, "mark_messages_seen"):
            await self._repo.mark_messages_seen(conversation_id, exclude_sender_id=user_id)
            conv.doctor_unread_count = 0
            await self._repo.flush()
        return [_message_out(m) for m in await self._repo.list_messages(conversation_id)]

    async def mark_read_patient(self, conversation_id: UUID, user_id: UUID) -> dict[str, object]:
        conv = await self._repo.get_for_patient(conversation_id, user_id)
        if conv is None:
            raise not_found()
        count = await self._repo.mark_messages_seen(conversation_id, exclude_sender_id=user_id)
        conv.patient_unread_count = 0
        await self._repo.flush()
        return {"ok": True, "marked_count": count}

    async def mark_read_doctor(self, conversation_id: UUID, user_id: UUID) -> dict[str, object]:
        conv = await self._repo.get_for_doctor(conversation_id, user_id)
        if conv is None:
            raise not_found()
        count = await self._repo.mark_messages_seen(conversation_id, exclude_sender_id=user_id)
        conv.doctor_unread_count = 0
        await self._repo.flush()
        return {"ok": True, "marked_count": count}

    async def upload_patient(
        self, conversation_id: UUID, user_id: UUID, upload: UploadFile
    ) -> AttachmentOut:
        conv = await self._repo.get_for_patient(conversation_id, user_id)
        if conv is None:
            raise not_found()
        saved = await save_chat_attachment(conversation_id=conversation_id, upload=upload)
        return AttachmentOut.model_validate(saved)

    async def upload_doctor(
        self, conversation_id: UUID, user_id: UUID, upload: UploadFile
    ) -> AttachmentOut:
        conv = await self._repo.get_for_doctor(conversation_id, user_id)
        if conv is None:
            raise not_found()
        saved = await save_chat_attachment(conversation_id=conversation_id, upload=upload)
        return AttachmentOut.model_validate(saved)

    async def send_patient(self, conversation_id: UUID, user_id: UUID, body: ChatIn) -> RowOut:
        conv = await self._repo.get_for_patient(conversation_id, user_id)
        if conv is None:
            raise not_found()
        msg, preview = await self._create_message(conversation_id, user_id, body)
        conv.last_message = preview
        conv.last_message_at = datetime.now(UTC)
        conv.doctor_unread_count += 1

        sender_name = "Patient"
        if hasattr(self._repo, "get_profile"):
            p = await self._repo.get_profile(user_id)
            if p and p.full_name:
                sender_name = p.full_name

        doctor = await self._repo.get_doctor(conv.doctor_id) if hasattr(self._repo, "get_doctor") else None
        if doctor and doctor.fcm_token and doctor.notifications_enabled is not False:
            title = f"New message from {sender_name}"
            push_preview = preview[:100] + ("..." if len(preview) > 100 else "")
            chat_data = {
                "type": "chat",
                "screen": "doctor_chat_room",
                "route": f"/doctor/messages/{conversation_id}",
                "conversation_id": str(conversation_id),
                "sender_id": str(user_id),
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
            }
            await send_fcm(doctor.fcm_token, title, push_preview, chat_data)

        await self._repo.flush()
        return _message_out(msg)

    async def send_doctor(self, conversation_id: UUID, user_id: UUID, body: ChatIn) -> RowOut:
        conv = await self._repo.get_for_doctor(conversation_id, user_id)
        if conv is None:
            raise not_found()
        msg, preview = await self._create_message(conversation_id, user_id, body)
        conv.last_message = preview
        conv.last_message_at = datetime.now(UTC)
        conv.patient_unread_count += 1

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
            push_preview = preview[:100] + ("..." if len(preview) > 100 else "")
            chat_data = {
                "type": "chat",
                "screen": "patient_chat_room",
                "route": f"/messages/{conversation_id}",
                "conversation_id": str(conversation_id),
                "sender_id": str(user_id),
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
            }
            await send_fcm(patient.fcm_token, title, push_preview, chat_data)

        await self._repo.flush()
        return _message_out(msg)

    async def _create_message(
        self, conversation_id: UUID, user_id: UUID, body: ChatIn
    ) -> tuple[ChatMessage, str]:
        message_type = (body.message_type or "text").strip().lower()
        preview_map = {"image": "Photo", "voice": "Voice message"}
        preview = preview_map.get(message_type, body.body.strip())
        if message_type == "text" and not preview:
            raise bad_request("Message cannot be empty.")

        validate_attachment_for_message(
            conversation_id=conversation_id,
            message_type=message_type,
            file_path=body.file_path,
            duration_ms=body.duration_ms,
        )

        msg = ChatMessage(
            conversation_id=conversation_id,
            sender_id=user_id,
            body=preview,
            message_type=message_type,
            file_path=body.file_path.strip() if body.file_path else None,
            duration_ms=body.duration_ms if message_type == "voice" else None,
            is_seen=False,
            seen_at=None,
        )
        self._repo.add(msg)
        return msg, preview
