from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import IntEnum
import os
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

class EnvironmentOptions(IntEnum):
    DEVELOPMENT = 1
    STAGING = 2
    PRODUCTION = 4

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    ENVIRONMENT: EnvironmentOptions = EnvironmentOptions.DEVELOPMENT
    
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_POOL_OVERFLOW: int = 10
    DATABASE_POOL_RECYCLE: int = 3600
    DATABASE_POOL_TIMEOUT: int = 30
    
    CORS_ALLOWED_ORIGINS: list[str] = ["*"]
    
    # Secrets
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 60 * 24

MySettings = Settings()
