"""Orchestrate create / get / delete / list models."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from flowjet_server.agent_runtime.events import RunFailed, RunRequest
from flowjet_server.agent_runtime.protocol import RuntimeBackend
from flowjet_server.openai_compat.errors import OpenAIError
from flowjet_server.openai_compat.projection import ProjectionEngine
from flowjet_server.openai_compat.schemas import (
    CreateResponseRequest,
    merge_flowjet_metadata,
    normalize_input,
)
from flowjet_server.openai_compat.store import InMemoryRunStore


def format_sse(payload: dict[str, Any]) -> str:
    event_type = payload.get("type", "message")
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


class ResponseService:
    def __init__(self, backend: RuntimeBackend, store: InMemoryRunStore | None = None) -> None:
        self.backend = backend
        self.store = store or InMemoryRunStore()

    async def list_models(self) -> dict[str, Any]:
        models = await self.backend.list_models()
        return {
            "object": "list",
            "data": [
                {
                    "id": m.id,
                    "object": "model",
                    "created": 0,
                    "owned_by": m.owned_by,
                }
                for m in models
            ],
        }

    def get(self, response_id: str) -> dict[str, Any]:
        body = self.store.get(response_id)
        if body is None:
            raise OpenAIError(
                f"No response found with id '{response_id}'.",
                code="response_not_found",
                param="id",
                status_code=404,
            )
        return body

    async def delete(self, response_id: str) -> dict[str, Any]:
        if not self.store.delete(response_id):
            raise OpenAIError(
                f"No response found with id '{response_id}'.",
                code="response_not_found",
                param="id",
                status_code=404,
            )
        await self.backend.delete_run(response_id)
        return {"id": response_id, "object": "response", "deleted": True}

    async def create(self, body: CreateResponseRequest) -> dict[str, Any]:
        response_id, engine, event_iter = await self._prepare(body)
        async for _payload in event_iter:
            pass
        final = engine.final_response()
        self.store.put(response_id, final)
        return final

    async def create_stream(self, body: CreateResponseRequest) -> AsyncIterator[str]:
        response_id, engine, event_iter = await self._prepare(body)
        async for payload in event_iter:
            yield format_sse(payload)
            if payload.get("type") in ("response.completed", "response.failed"):
                self.store.put(response_id, engine.final_response())

    async def _prepare(
        self, body: CreateResponseRequest
    ) -> tuple[str, ProjectionEngine, AsyncIterator[dict[str, Any]]]:
        models = {m.id for m in await self.backend.list_models()}
        if body.model not in models:
            raise OpenAIError(
                f"Model '{body.model}' not found.",
                code="model_not_found",
                param="model",
                status_code=404,
            )

        opts = body.flowjet
        projection = opts.projection if opts else "report"
        session = opts.session if opts else None
        metadata = merge_flowjet_metadata(opts)
        response_id = f"resp_{uuid4().hex}"
        engine = ProjectionEngine(projection, response_id, body.model)

        request = RunRequest(
            model=body.model,
            input_text=normalize_input(body.input),
            session=session,
            metadata=metadata,
            run_id=response_id,
        )

        self.store.put(
            response_id,
            {
                "id": response_id,
                "object": "response",
                "status": "in_progress",
                "model": body.model,
                "output": [],
                "usage": None,
            },
        )

        async def gen() -> AsyncIterator[dict[str, Any]]:
            try:
                async for runtime_event in self.backend.stream_run(request):
                    for payload in engine.handle(runtime_event):
                        yield payload
            except Exception as exc:  # noqa: BLE001
                for payload in engine.handle(RunFailed(message=str(exc) or type(exc).__name__)):
                    yield payload
                self.store.put(response_id, engine.final_response())

        return response_id, engine, gen()
