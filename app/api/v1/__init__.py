from fastapi import APIRouter

api_v1_router = APIRouter(prefix="/api/v1")

@api_v1_router.get("/health")
async def health_check():
    return {"status": "ok"}
