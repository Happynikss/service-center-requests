from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_title: str = "Сервісний центр «ТехноСервіс» — Система керування зверненнями"
    app_env: str = "development"
    secret_key: str = "change-this-to-a-long-random-secret-key-2026"
    access_token_expire_minutes: int = 480
    database_url: str = "postgresql+psycopg://service_user:service_pass@localhost:5433/service_center_db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()