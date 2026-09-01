from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import MySettings

async_engine = create_async_engine(
    url=MySettings.DATABASE_URL,
    future=True,
    pool_size=MySettings.DATABASE_POOL_SIZE,
    max_overflow=MySettings.DATABASE_POOL_OVERFLOW,
    pool_recycle=MySettings.DATABASE_POOL_RECYCLE,
    pool_timeout=MySettings.DATABASE_POOL_TIMEOUT,
    pool_pre_ping=True,  # Enable connection health checks
    echo=False,          # Disable SQL logging in production
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    async_engine, autoflush=False, expire_on_commit=False, class_=AsyncSession
)
