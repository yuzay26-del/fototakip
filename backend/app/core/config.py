"""Uygulama ayarları.

Çalışma modu (termux / server) yalnızca buradan okunur. Kodun geri kalanı
mod adını kontrol etmez; farklılık adaptör seçimindedir.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_mode: Literal["termux", "server"] = "termux"
    database_url: str = "sqlite+aiosqlite:///./data/fototakip.db"
    storage_backend: Literal["local", "s3"] = "local"
    queue_backend: Literal["inprocess", "redis"] = "inprocess"
    secret_key: str = "degistir-beni"
    media_root: Path = Path("./data/media")
    redis_url: str = "redis://localhost:6379/0"
    web_dist: Path | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
