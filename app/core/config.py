import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "PoshanScan Backend"
    API_V1_STR: str = "/api/v1"
    PORT: int = 8000
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./poshanscan.db"

    # Security & JWT
    JWT_SECRET: str = "poshanscan-gtbit-secret-key-2026-cse-ds"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # AI/CV Microservice (Yash's service)
    CV_SERVICE_URL: str = "http://localhost:8001"
    MOCK_CV: bool = True

    # Image upload directory
    UPLOAD_DIR: str = "./uploads"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
