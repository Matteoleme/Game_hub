from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Game Hub"
    environment: str = "development"
    port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./data/game_hub.db"
    session_secret: str = "change-me-in-development"
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
