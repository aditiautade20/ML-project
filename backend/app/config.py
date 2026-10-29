from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Security
    SECRET_KEY: str = "dev-invoiceiq-secret-key-32-chars-minimum-entropy!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database: default relative path
    DATABASE_URL: str = "sqlite:///./data/invoiceiq.db"

    # Uploads Configuration
    UPLOAD_DIR: str = "data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def resolved_database_url(self) -> str:
        """Ensures relative SQLite database paths are anchored to the backend root directory."""
        if self.DATABASE_URL.startswith("sqlite:///") and not self.DATABASE_URL.startswith("sqlite:///:memory:"):
            raw_path = self.DATABASE_URL.replace("sqlite:///", "")
            path_obj = Path(raw_path)
            if not path_obj.is_absolute():
                resolved = (BASE_DIR / path_obj).resolve()
                return f"sqlite:///{resolved.as_posix()}"
        return self.DATABASE_URL

    @property
    def resolved_upload_dir(self) -> Path:
        """Ensures upload directory is created and anchored to the backend root directory."""
        path_obj = Path(self.UPLOAD_DIR)
        if not path_obj.is_absolute():
            resolved = (BASE_DIR / path_obj).resolve()
        else:
            resolved = path_obj
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
