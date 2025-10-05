from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BEATMAPR_", case_sensitive=False)

    database_url: str = f"sqlite:///beatmapr.app.db"
    osu_client_id: int | None = None
    osu_client_secret: str | None = None
    akatsuki_base_url: str = "https://akatsuki.gg/api/v1"
    request_timeout_seconds: float = 15.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
