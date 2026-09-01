from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import MySettings
from app.api.exception_handler import register_exception_handlers
from app.persistence.sqlalchemy.map_registry import init_mapper

def register_router(app: FastAPI) -> FastAPI:
    from app.api.v1 import api_v1_router
    app.include_router(api_v1_router)
    return app

def create_app():
    app = FastAPI(title=f"My Application - {MySettings.ENVIRONMENT.name}")

    init_mapper()
    register_router(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=MySettings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return register_exception_handlers(app)

__all__ = ["create_app"]
