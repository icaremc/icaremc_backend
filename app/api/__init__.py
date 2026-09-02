from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import MySettings
from app.api.exception_handler import register_exception_handlers
from app.persistence.sqlalchemy.map_registry import init_mapper
from app.persistence.sqlalchemy import connection


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # fastapi-python skill: lifespan for startup/shutdown (dispose pool cleanly)
    yield
    await connection.async_engine.dispose()


def register_router(app: FastAPI) -> FastAPI:
    from app.api.v1 import api_v1_router

    app.include_router(api_v1_router)
    return app


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"iCare MC - {MySettings.ENVIRONMENT.name}",
        lifespan=lifespan,
    )

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
