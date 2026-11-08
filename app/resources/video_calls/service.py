from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
import zlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import MySettings
from app.core.services.agora_token import Role_Publisher, RtcTokenBuilder
from app.persistence.sqlalchemy.models import ChatConversation, DoctorProfile, Profile, VideoCallSession
from app.resources.errors import bad_request, conflict, not_found, service_unavailable
from app.resources.push.fcm import send_fcm
from app.resources.video_calls.schemas import EndVideoCallOut, VideoCallJoinOut, VideoCallStatusOut


def _agora_uid(user_id: UUID) -> int:
    """Stable Agora int uid in 1..2^31-1 from UUID."""
    value = zlib.crc32(user_id.bytes) & 0x7FFFFFFF
    return value or 1


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _remaining(ends_at: datetime, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=UTC)
    return max(0, int((ends_at - now).total_seconds()))


def _require_agora() -> tuple[str, str]:
    app_id = (MySettings.AGORA_APP_ID or "").strip()
    cert = (MySettings.AGORA_APP_CERTIFICATE or "").strip()
    if not app_id or not cert:
        raise service_unavailable("Video calling is not configured.")
    return app_id, cert


def _build_token(channel: str, uid: int, expire_seconds: int) -> str:
    app_id, cert = _require_agora()
    expire = max(30, expire_seconds)
    return RtcTokenBuilder.build_token_with_uid(
        app_id,
        cert,
        channel,
        uid,
        Role_Publisher,
        expire,
        expire,
    )


class VideoCallService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _get_conversation(self, conversation_id: UUID) -> ChatConversation:
        conv = (
            await self._db.execute(select(ChatConversation).where(ChatConversation.id == conversation_id))
        ).scalar_one_or_none()
        if conv is None:
            raise not_found("Conversation not found.")
        return conv

    async def _expire_if_needed(self, session: VideoCallSession) -> VideoCallSession:
        if session.status in {"ended", "expired"}:
            return session
        if _remaining(session.ends_at) <= 0:
            session.status = "expired"
            session.ended_at = datetime.now(UTC)
            await self._db.flush()
        return session

    async def _active_for_doctor(self, doctor_id: UUID) -> VideoCallSession | None:
        rows = (
            await self._db.execute(
                select(VideoCallSession).where(
                    VideoCallSession.doctor_id == doctor_id,
                    VideoCallSession.status.in_(("ringing", "active")),
                )
            )
        ).scalars().all()
        for row in rows:
            await self._expire_if_needed(row)
            if row.status in {"ringing", "active"}:
                return row
        return None

    async def _active_for_conversation(self, conversation_id: UUID) -> VideoCallSession | None:
        rows = (
            await self._db.execute(
                select(VideoCallSession)
                .where(
                    VideoCallSession.conversation_id == conversation_id,
                    VideoCallSession.status.in_(("ringing", "active")),
                )
                .order_by(VideoCallSession.started_at.desc())
            )
        ).scalars().all()
        for row in rows:
            await self._expire_if_needed(row)
            if row.status in {"ringing", "active"}:
                return row
        return None

    def _join_out(self, session: VideoCallSession, user_id: UUID, role: str) -> VideoCallJoinOut:
        remaining = _remaining(session.ends_at)
        if remaining <= 0:
            raise bad_request("This video call has ended.")
        uid = _agora_uid(user_id)
        token = _build_token(session.channel_name, uid, remaining)
        app_id, _ = _require_agora()
        return VideoCallJoinOut(
            id=session.id,
            conversation_id=session.conversation_id,
            appointment_id=session.appointment_id,
            channel_name=session.channel_name,
            app_id=app_id,
            token=token,
            uid=uid,
            status=session.status,
            started_at=_iso(session.started_at),
            ends_at=_iso(session.ends_at),
            remaining_seconds=remaining,
            warn_seconds=MySettings.VIDEO_CALL_WARN_SECONDS,
            role=role,
        )

    def _status_out(self, session: VideoCallSession) -> VideoCallStatusOut:
        return VideoCallStatusOut(
            id=session.id,
            conversation_id=session.conversation_id,
            appointment_id=session.appointment_id,
            channel_name=session.channel_name,
            status=session.status,
            started_at=_iso(session.started_at),
            ends_at=_iso(session.ends_at),
            remaining_seconds=_remaining(session.ends_at),
            warn_seconds=MySettings.VIDEO_CALL_WARN_SECONDS,
        )

    async def start_doctor(self, doctor_id: UUID, conversation_id: UUID) -> VideoCallJoinOut:
        conv = await self._get_conversation(conversation_id)
        if conv.doctor_id != doctor_id:
            raise not_found("Conversation not found.")

        existing = await self._active_for_doctor(doctor_id)
        if existing is not None:
            if existing.conversation_id == conversation_id:
                return self._join_out(existing, doctor_id, "doctor")
            raise conflict("You already have an active video call with another patient.")

        max_seconds = max(60, int(MySettings.VIDEO_CALL_MAX_SECONDS or 900))
        now = datetime.now(UTC)
        session = VideoCallSession(
            conversation_id=conv.id,
            appointment_id=conv.appointment_id,
            doctor_id=conv.doctor_id,
            patient_id=conv.patient_id,
            channel_name=f"vc_{uuid4().hex[:24]}",
            status="ringing",
            started_at=now,
            ends_at=now + timedelta(seconds=max_seconds),
        )
        self._db.add(session)
        await self._db.flush()

        doctor = (
            await self._db.execute(select(DoctorProfile).where(DoctorProfile.id == doctor_id))
        ).scalar_one_or_none()
        patient = (
            await self._db.execute(select(Profile).where(Profile.id == conv.patient_id))
        ).scalar_one_or_none()

        doc_name = "Your doctor"
        if doctor:
            names = f"{getattr(doctor, 'first_name', '') or ''} {getattr(doctor, 'last_name', '') or ''}".strip()
            if names:
                doc_name = names if names.lower().startswith("dr.") else f"Dr. {names}"

        if patient and patient.fcm_token and patient.notifications_enabled is not False:
            await send_fcm(
                patient.fcm_token,
                "Incoming video call",
                f"{doc_name} is calling you",
                {
                    "type": "video_call",
                    "screen": "patient_video_call",
                    "route": "/incoming-video-call",
                    "call_id": str(session.id),
                    "conversation_id": str(conv.id),
                    "caller_name": doc_name,
                    "click_action": "FLUTTER_NOTIFICATION_CLICK",
                },
            )

        return self._join_out(session, doctor_id, "doctor")

    async def join_doctor(self, doctor_id: UUID, call_id: UUID) -> VideoCallJoinOut:
        session = await self._get_session(call_id)
        if session.doctor_id != doctor_id:
            raise not_found()
        await self._expire_if_needed(session)
        if session.status in {"ended", "expired"}:
            raise bad_request("This video call has ended.")
        if session.status == "ringing":
            session.status = "active"
            await self._db.flush()
        return self._join_out(session, doctor_id, "doctor")

    async def join_patient(self, patient_id: UUID, call_id: UUID) -> VideoCallJoinOut:
        session = await self._get_session(call_id)
        if session.patient_id != patient_id:
            raise not_found()
        await self._expire_if_needed(session)
        if session.status in {"ended", "expired"}:
            raise bad_request("This video call has ended.")
        if session.status == "ringing":
            session.status = "active"
            await self._db.flush()
        return self._join_out(session, patient_id, "patient")

    async def active_for_patient(self, patient_id: UUID, conversation_id: UUID) -> VideoCallStatusOut | None:
        conv = await self._get_conversation(conversation_id)
        if conv.patient_id != patient_id:
            raise not_found()
        session = await self._active_for_conversation(conversation_id)
        if session is None:
            return None
        return self._status_out(session)

    async def active_for_doctor(self, doctor_id: UUID, conversation_id: UUID) -> VideoCallStatusOut | None:
        conv = await self._get_conversation(conversation_id)
        if conv.doctor_id != doctor_id:
            raise not_found()
        session = await self._active_for_conversation(conversation_id)
        if session is None:
            return None
        return self._status_out(session)

    async def end_doctor(self, doctor_id: UUID, call_id: UUID) -> EndVideoCallOut:
        session = await self._get_session(call_id)
        if session.doctor_id != doctor_id:
            raise not_found()
        return await self._end(session, doctor_id)

    async def end_patient(self, patient_id: UUID, call_id: UUID) -> EndVideoCallOut:
        session = await self._get_session(call_id)
        if session.patient_id != patient_id:
            raise not_found()
        return await self._end(session, patient_id)

    async def _end(self, session: VideoCallSession, user_id: UUID) -> EndVideoCallOut:
        if session.status not in {"ended", "expired"}:
            session.status = "ended"
            session.ended_at = datetime.now(UTC)
            session.ended_by = user_id
            await self._db.flush()
        return EndVideoCallOut(ok=True, id=session.id, status=session.status)

    async def _get_session(self, call_id: UUID) -> VideoCallSession:
        session = (
            await self._db.execute(select(VideoCallSession).where(VideoCallSession.id == call_id))
        ).scalar_one_or_none()
        if session is None:
            raise not_found("Video call not found.")
        return session
