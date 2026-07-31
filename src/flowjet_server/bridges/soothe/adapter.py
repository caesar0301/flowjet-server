"""SootheAgentAdapter — full SootheRunner for the isolation ThreadPool."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from flowjet_server.agent_runtime.events import RuntimeEvent
from flowjet_server.agent_runtime.isolation.request import IsolatedRunRequest
from flowjet_server.bridges.soothe.mapping import iter_soothe_runtime_events


def create_soothe_runner(config_path: str | Path | None = None) -> Any:
    try:
        from soothe.config import SootheConfig
        from soothe.runner import SootheRunner
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "soothe is not installed. Reinstall flowjet-server or set FLOWJET_BACKEND=fake."
        ) from exc
    if config_path is not None:
        path = Path(config_path).expanduser()
        config = SootheConfig.from_yaml_file(str(path)) if path.is_file() else SootheConfig()
    else:
        config = SootheConfig()
    return SootheRunner(config=config)


class SootheAgentAdapter:
    """AgentAdapter wrapping a SootheRunner (one instance per pool worker)."""

    def __init__(
        self,
        runner: Any | None = None,
        *,
        config_path: str | Path | None = None,
    ) -> None:
        self._runner = runner
        self._config_path = config_path

    def _ensure(self) -> Any:
        if self._runner is None:
            self._runner = create_soothe_runner(self._config_path)
        return self._runner

    async def astream(self, req: IsolatedRunRequest) -> AsyncIterator[RuntimeEvent]:
        runner = self._ensure()
        async for event in iter_soothe_runtime_events(
            runner,
            run_id=req.run_id,
            model=req.model,
            session=req.session,
            input_text=req.input_text,
            workspace=str(req.workspace),
            thread_id=req.effective_thread_id(),
        ):
            yield event

    def prepare_for_request(self) -> None:
        runner = self._runner
        if runner is not None and hasattr(runner, "prepare_for_request"):
            runner.prepare_for_request()

    async def cleanup(self) -> None:
        runner = self._runner
        if runner is not None and hasattr(runner, "cleanup"):
            result = runner.cleanup()
            if hasattr(result, "__await__"):
                await result
        self._runner = None


def soothe_adapter_factory(*, config_path: str | Path | None = None):
    def factory() -> SootheAgentAdapter:
        return SootheAgentAdapter(config_path=config_path)

    return factory


def build_isolating_soothe_backend(
    *,
    models: list[str] | None = None,
    config_path: str | Path | None = None,
    home: Path | str | None = None,
    pool_settings: Any = None,
) -> Any:
    from flowjet_server.agent_runtime.isolation import IsolatingRuntimeBackend, PoolSettings

    settings = pool_settings if pool_settings is not None else PoolSettings()

    def factory() -> SootheAgentAdapter:
        return SootheAgentAdapter(config_path=config_path)

    return IsolatingRuntimeBackend(
        models=models,
        adapter_factory=factory,
        pool_settings=settings,
        home=home,
    )
