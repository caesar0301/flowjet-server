"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from flowjet_server.agent_runtime.fake import FakeRuntimeBackend
from flowjet_server.agent_runtime.protocol import RuntimeBackend
from flowjet_server.config import Settings
from flowjet_server.http.auth import require_api_key
from flowjet_server.openai_compat.errors import OpenAIError, error_body
from flowjet_server.openai_compat.routes import create_router
from flowjet_server.openai_compat.service import ResponseService
from flowjet_server.openai_compat.store import InMemoryRunStore


def build_backend(settings: Settings) -> RuntimeBackend:
    if settings.backend == "nano":
        from flowjet_server.bridges.nano import build_isolating_nano_backend

        return build_isolating_nano_backend(
            models=settings.model_ids(),
            config_path=settings.nano_config,
            home=settings.home_path(),
            pool_settings=settings.pool_settings(),
        )
    if settings.backend == "soothe":
        from flowjet_server.bridges.soothe import build_isolating_soothe_backend

        return build_isolating_soothe_backend(
            models=settings.model_ids(),
            config_path=settings.soothe_config,
            home=settings.home_path(),
            pool_settings=settings.pool_settings(),
        )
    return FakeRuntimeBackend(models=settings.model_ids())


def create_app(
    settings: Settings | None = None,
    backend: RuntimeBackend | None = None,
) -> FastAPI:
    settings = settings or Settings()
    backend = backend or build_backend(settings)
    store = InMemoryRunStore()
    service = ResponseService(backend=backend, store=store)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        shutdown = getattr(app.state.backend, "shutdown", None)
        if shutdown is not None:
            result = shutdown()
            if hasattr(result, "__await__"):
                await result

    app = FastAPI(title="flowjet-server", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.api_key = settings.api_key
    app.state.backend = backend
    app.state.service = service

    auth = require_api_key if settings.api_key else None
    app.include_router(create_router(auth_dependency=auth))

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(OpenAIError)
    async def openai_error_handler(_request: Request, exc: OpenAIError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=error_body(exc))

    return app


# Default ASGI app for `uvicorn flowjet_server.http.app:app`
app = create_app()
