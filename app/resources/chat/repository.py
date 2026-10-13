from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.sqlalchemy.models import ChatConversation, ChatMessage, DoctorProfile, Profile


class ChatRepository(Protocol):
    async def list_for_patient(self, user_id: UUID) -> list[ChatConversation]: ...
    async def list_for_doctor(self, user_id: UUID) -> list[ChatConversation]: ...
    async def get_for_patient(self, conversation_id: UUID, user_id: UUID) -> ChatConversation | None: ...
    async def get_for_doctor(self, conversation_id: UUID, user_id: UUID) -> ChatConversation | None: ...
    async def list_messages(self, conversation_id: UUID) -> list[ChatMessage]: ...
    async def get_profile(self, user_id: UUID) -> Profile | None: ...
    async def get_doctor(self, user_id: UUID) -> DoctorProfile | None: ...
    def add(self, obj: object) -> None: ...
    async def flush(self) -> None: ...


class SqlAlchemyChatRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_for_patient(self, user_id: UUID) -> list[ChatConversation]:
        return list(
            (await self._db.execute(select(ChatConversation).where(ChatConversation.patient_id == user_id)))
            .scalars()
            .all()
        )

    async def list_for_doctor(self, user_id: UUID) -> list[ChatConversation]:
        return list(
            (await self._db.execute(select(ChatConversation).where(ChatConversation.doctor_id == user_id)))
            .scalars()
            .all()
        )

    async def get_for_patient(self, conversation_id: UUID, user_id: UUID) -> ChatConversation | None:
        return (
            await self._db.execute(
                select(ChatConversation).where(
                    ChatConversation.id == conversation_id, ChatConversation.patient_id == user_id
                )
            )
        ).scalar_one_or_none()

    async def get_for_doctor(self, conversation_id: UUID, user_id: UUID) -> ChatConversation | None:
        return (
            await self._db.execute(
                select(ChatConversation).where(
                    ChatConversation.id == conversation_id, ChatConversation.doctor_id == user_id
                )
            )
        ).scalar_one_or_none()

    async def list_messages(self, conversation_id: UUID) -> list[ChatMessage]:
        return list(
            (
                await self._db.execute(
                    select(ChatMessage).where(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.created_at)
                )
            )
            .scalars()
            .all()
        )

    async def get_profile(self, user_id: UUID) -> Profile | None:
        return (await self._db.execute(select(Profile).where(Profile.id == user_id))).scalar_one_or_none()

    async def get_doctor(self, user_id: UUID) -> DoctorProfile | None:
        return (await self._db.execute(select(DoctorProfile).where(DoctorProfile.id == user_id))).scalar_one_or_none()

    def add(self, obj: object) -> None:
        self._db.add(obj)

    async def flush(self) -> None:
        await self._db.flush()
