from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.security.deps import RequireDoctor, RequirePatient
from app.persistence.sqlalchemy.deps import DbDep
from app.resources.video_calls.schemas import (
    EndVideoCallOut,
    StartVideoCallIn,
    VideoCallJoinOut,
    VideoCallStatusOut,
)
from app.resources.video_calls.service import VideoCallService

router = APIRouter(tags=["video-calls"])
doctor_router = APIRouter(prefix="/doctor", tags=["doctor-video-calls"])


def get_video_call_service(db: DbDep) -> VideoCallService:
    return VideoCallService(db)


VideoCallDep = Annotated[VideoCallService, Depends(get_video_call_service)]


@doctor_router.post("/video-calls", response_model=VideoCallJoinOut)
async def start_video_call(
    body: StartVideoCallIn,
    user: RequireDoctor,
    svc: VideoCallDep,
) -> VideoCallJoinOut:
    return await svc.start_doctor(user.id, body.conversation_id)


@doctor_router.get("/video-calls/active", response_model=VideoCallStatusOut | None)
async def doctor_active_video_call(
    conversation_id: UUID,
    user: RequireDoctor,
    svc: VideoCallDep,
) -> VideoCallStatusOut | None:
    return await svc.active_for_doctor(user.id, conversation_id)


@doctor_router.post("/video-calls/{call_id}/join", response_model=VideoCallJoinOut)
async def doctor_join_video_call(
    call_id: UUID,
    user: RequireDoctor,
    svc: VideoCallDep,
) -> VideoCallJoinOut:
    return await svc.join_doctor(user.id, call_id)


@doctor_router.post("/video-calls/{call_id}/end", response_model=EndVideoCallOut)
async def doctor_end_video_call(
    call_id: UUID,
    user: RequireDoctor,
    svc: VideoCallDep,
) -> EndVideoCallOut:
    return await svc.end_doctor(user.id, call_id)


@router.get("/video-calls/active", response_model=VideoCallStatusOut | None)
async def patient_active_video_call(
    conversation_id: UUID,
    user: RequirePatient,
    svc: VideoCallDep,
) -> VideoCallStatusOut | None:
    return await svc.active_for_patient(user.id, conversation_id)


@router.post("/video-calls/{call_id}/join", response_model=VideoCallJoinOut)
async def patient_join_video_call(
    call_id: UUID,
    user: RequirePatient,
    svc: VideoCallDep,
) -> VideoCallJoinOut:
    return await svc.join_patient(user.id, call_id)


@router.post("/video-calls/{call_id}/end", response_model=EndVideoCallOut)
async def patient_end_video_call(
    call_id: UUID,
    user: RequirePatient,
    svc: VideoCallDep,
) -> EndVideoCallOut:
    return await svc.end_patient(user.id, call_id)
