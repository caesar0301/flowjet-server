"""NanoAgentAdapter — soothe-nano runner for the isolation ThreadPool."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from flowjet_server.agent_runtime.events import RuntimeEvent
from flowjet_server.agent_runtime.isolation.request import IsolatedRunRequest
from flowjet_server.bridges.nano.mapping import iter_nano_runtime_events


def create_nano_agent_instance(config_path: str | Path | None = None) -> Any:
    try:
        from soothe_nano import create_nano_agent
        from soothe_nano.config import SOOTHE_HOME, SootheConfig
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "soothe-nano is not installed (expected via the soothe dependency). "
            "Reinstall flowjet-server or set FLOWJET_BACKEND=fake."
        ) from exc
    path = Path(config_path).expanduser() if config_path else SOOTHE_HOME / "config" / "nano.yml"
    config = SootheConfig.from_yaml_file(str(path)) if path.is_file() else SootheConfig()
    return create_nano_agent(config)


class NanoAgentAdapter:
    """AgentAdapter wrapping a SootheNanoAgent (one instance per pool worker)."""

    def __init__(
        self,
        agent: Any | None = None,
        *,
        config_path: str | Path | None = None,
    ) -> None:
        self._agent = agent
        self._config_path = config_path

    def _ensure(self) -> Any:
        if self._agent is None:
            self._agent = create_nano_agent_instance(self._config_path)
        return self._agent

    async def astream(self, req: IsolatedRunRequest) -> AsyncIterator[RuntimeEvent]:
        agent = self._ensure()
        async for event in iter_nano_runtime_events(
            agent,
            run_id=req.run_id,
            model=req.model,
            session=req.session,
            input_text=req.input_text,
            workspace=str(req.workspace),
            thread_id=req.effective_thread_id(),
        ):
            yield event

    def prepare_for_request(self) -> None:
        # Nano agent has no SootheRunner.prepare_for_request; graph state is
        # request-local via configurable.thread_id / workspace.
        return None

    async def cleanup(self) -> None:
        self._agent = None


def nano_adapter_factory(*, config_path: str | Path | None = None):
    """Return a zero-arg factory suitable for ThreadPool / IsolatingRuntimeBackend."""

    def factory() -> NanoAgentAdapter:
        return NanoAgentAdapter(config_path=config_path)

    return factory
