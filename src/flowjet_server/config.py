"""Server settings from environment."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLOWJET_", extra="ignore")

    api_key: str | None = None
    backend: str = "fake"  # fake | nano
    models: str = "default"
    host: str = "0.0.0.0"
    port: int = 8080

    def model_ids(self) -> list[str]:
        return [m.strip() for m in self.models.split(",") if m.strip()]
