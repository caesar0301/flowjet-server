"""RuntimeBackend that admits, resolves workspaces, and submits to ThreadPool."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

from flowjet_server.agent_runtime.events import ModelInfo, RunRequest, RuntimeEvent
from flowjet_server.agent_runtime.isolation.adapter import AdapterFactory
from flowjet_server.agent_runtime.isolation.admission import SessionAdmission
from flowjet_server.agent_runtime.isolation.pool import PoolSettings, ThreadPool
from flowjet_server.agent_runtime.isolation.request import IsolatedRunRequest
from flowjet_server.agent_runtime.isolation.workspace import WorkspaceResolver


class IsolatingRuntimeBackend:
    """Pool-backed RuntimeBackend for nano / soothe adapters."""

    def __init__(
        self,
        *,
        models: list[str] | None = None,
        adapter_factory: AdapterFactory,
        pool_settings: PoolSettings | None = None,
        home: Path | str | None = None,
        admission: SessionAdmission | None = None,
        pool: ThreadPool | None = None,
    ) -> None:
        self._models = models or ["default"]
        home_path = Path(home).expanduser() if home else Path.home() / ".flowjet"
        self._workspaces = WorkspaceResolver(home_path)
        self._admission = admission or SessionAdmission()
        self._pool = pool or ThreadPool(adapter_factory, pool_settings)
        self._started = False

    @property
    def pool(self) -> ThreadPool:
        return self._pool

    @property
    def workspaces(self) -> WorkspaceResolver:
        return self._workspaces

    async def _ensure_started(self) -> None:
        if not self._started:
            await self._pool.start()
            self._started = True

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id=m) for m in self._models]

    async def delete_run(self, run_id: str) -> None:
        self._pool.cancel_run(run_id)

    async def stream_run(self, request: RunRequest) -> AsyncIterator[RuntimeEvent]:
        await self._ensure_started()
        session = request.session or f"fj-{uuid4()}"
        run_id = request.run_id or f"resp_{uuid4().hex}"
        workspace = self._workspaces.resolve(session, request.metadata)
        isolated = IsolatedRunRequest(
            run_id=run_id,
            session=session,
            input_text=request.input_text,
            model=request.model,
            workspace=workspace,
            thread_id=session,
            metadata=request.metadata,
        )
        async with self._admission.admit(session):
            async for event in self._pool.submit(isolated):
                yield event

    async def shutdown(self) -> None:
        await self._pool.shutdown()
        self._started = False
