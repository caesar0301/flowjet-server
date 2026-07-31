"""Server settings from environment."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from flowjet_server.agent_runtime.isolation.pool import PoolSettings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLOWJET_", extra="ignore")

    api_key: str | None = None
    models: str = "default"
    host: str = "0.0.0.0"
    port: int = 8080

    home: str = Field(default="~/.flowjet")
    thread_pool_min: int = 2
    thread_pool_max: int = 8
    thread_pool_idle_timeout: float = 300.0
    max_requests_per_worker: int = 100
    reuse_runner: bool = True
    request_timeout: float = 0.0
    ready_timeout: float = 30.0
    allow_external_workspace: bool = False
    nano_config: str | None = None

    def model_ids(self) -> list[str]:
        return [m.strip() for m in self.models.split(",") if m.strip()]

    def home_path(self) -> Path:
        return Path(self.home).expanduser().resolve()

    def pool_settings(self) -> PoolSettings:
        return PoolSettings(
            min_size=max(1, self.thread_pool_min),
            max_size=max(self.thread_pool_min, self.thread_pool_max),
            idle_timeout_seconds=self.thread_pool_idle_timeout,
            max_requests_per_worker=self.max_requests_per_worker,
            reuse_runner=self.reuse_runner,
            request_timeout_seconds=self.request_timeout,
            ready_timeout_seconds=self.ready_timeout,
        )
