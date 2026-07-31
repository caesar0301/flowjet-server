"""NanoRuntimeBackend — maps soothe-nano streams to Agent Runtime events.

Requires optional extra: ``pip install flowjet-server[nano]``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import uuid4

from flowjet_server.agent_runtime.events import (
    InterruptWaiting,
    ModelInfo,
    OutputTextDelta,
    Progress,
    RunCompleted,
    RunFailed,
    RunRequest,
    RunStarted,
    RuntimeEvent,
    ToolCompleted,
    ToolStarted,
)

_SKIP_CUSTOM_TYPES = frozenset(
    {
        "soothe.stream.end",
        "soothe.protocol.message.received",
        "soothe.internal.policy.checked",
        "soothe.internal.plugin.health_checked",
    }
)


def _ai_text(message: Any) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _map_custom(data: dict[str, Any]) -> Progress | None:
    event_type = str(data.get("type") or "").strip()
    if not event_type or event_type in _SKIP_CUSTOM_TYPES:
        return None
    if event_type.startswith("soothe.output."):
        return None
    short = event_type[7:] if event_type.startswith("soothe.") else event_type
    parts = short.split(".")
    domain = parts[0] if parts else "agent"
    action = parts[-1] if parts else ""
    # Never forward prompts / tool args
    if any(k in data for k in ("prompt", "arguments", "args", "system_prompt")):
        # Still allow a coarse label without leaking values
        tool = data.get("tool") or data.get("name")
        if isinstance(tool, str) and domain in {"tool", "mcp"}:
            return Progress(stage=tool, message=f"{action or 'Running'} {tool}".strip())
        return Progress(stage=domain.title(), message=action.replace("_", " ").title() or "Working")
    message = data.get("message") or data.get("action_preview") or action.replace("_", " ")
    stage = str(data.get("tool") or data.get("name") or domain).title()
    return Progress(stage=str(stage), message=str(message or "Working"))


class NanoRuntimeBackend:
    """RuntimeBackend backed by soothe-nano (optional dependency)."""

    def __init__(
        self,
        models: list[str] | None = None,
        agent: Any | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        self._models = models or ["default"]
        self._agent = agent
        self._config_path = Path(config_path).expanduser() if config_path else None

    def _ensure_agent(self) -> Any:
        if self._agent is not None:
            return self._agent
        try:
            from soothe_nano import create_nano_agent
            from soothe_nano.config import SOOTHE_HOME, SootheConfig
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "soothe-nano is not installed. Install flowjet-server[nano] "
                "or set FLOWJET_BACKEND=fake."
            ) from exc
        config_path = self._config_path or SOOTHE_HOME / "config" / "nano.yml"
        config = (
            SootheConfig.from_yaml_file(str(config_path))
            if config_path.is_file()
            else SootheConfig()
        )
        self._agent = create_nano_agent(config)
        return self._agent

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id=m) for m in self._models]

    async def delete_run(self, run_id: str) -> None:
        return None

    async def stream_run(self, request: RunRequest) -> AsyncIterator[RuntimeEvent]:
        try:
            from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("langchain-core is required for the nano bridge") from exc

        agent = self._ensure_agent()
        run_id = request.run_id or f"resp_{uuid4().hex}"
        session = request.session or f"fj-{uuid4()}"
        yield RunStarted(run_id=run_id, model=request.model, session=session)

        messages = [HumanMessage(content=request.input_text)]
        config = {"configurable": {"thread_id": session}}
        answer = ""
        composing = False
        open_tools: dict[str, str] = {}

        try:
            async for chunk in agent.astream(
                {"messages": messages},
                config=config,
                stream_mode=["messages", "updates", "custom"],
                subgraphs=True,
            ):
                if not isinstance(chunk, tuple) or len(chunk) != 3:
                    continue
                _ns, mode, data = chunk

                if mode == "custom" and isinstance(data, dict):
                    mapped = _map_custom(data)
                    if mapped:
                        yield mapped
                    continue

                if mode == "updates" and isinstance(data, dict) and "__interrupt__" in data:
                    yield InterruptWaiting(message="Waiting for input…")
                    continue

                if mode != "messages":
                    continue
                if not isinstance(data, tuple) or len(data) != 2:
                    continue
                message_obj, _meta = data

                if isinstance(message_obj, AIMessage):
                    tool_calls = getattr(message_obj, "tool_calls", None) or []
                    if tool_calls:
                        # Any prior assistant text was pre-tool narration, not
                        # the final answer. Match flowjet-agent's reset behavior.
                        answer = ""
                        composing = False
                        for tc in tool_calls:
                            if isinstance(tc, dict):
                                name = tc.get("name")
                                tc_id = tc.get("id")
                            else:
                                name = getattr(tc, "name", None)
                                tc_id = getattr(tc, "id", None)
                            if name:
                                open_tools[str(tc_id or name)] = str(name)
                                call = str(tc_id) if tc_id else None
                                yield ToolStarted(tool=str(name), call_id=call)
                        continue
                    text = _ai_text(message_obj)
                    if text:
                        # Buffer until the run ends. Emitting immediately could
                        # leak pre-tool narration that is later superseded.
                        if text.startswith(answer):
                            delta = text[len(answer) :]
                        elif answer.startswith(text):
                            delta = ""
                        else:
                            delta = text
                        if delta:
                            answer = text if text.startswith(answer) else answer + delta
                            # A milestone, not a transcript: nano streams the
                            # answer token by token, and forwarding each chunk
                            # would both spam the client and surface narration
                            # that a later tool call may supersede.
                            if not composing:
                                composing = True
                                yield Progress(stage="Working", message="Composing response…")

                elif isinstance(message_obj, ToolMessage):
                    tc_id = getattr(message_obj, "tool_call_id", None)
                    name = (
                        open_tools.pop(str(tc_id), None)
                        or getattr(message_obj, "name", None)
                        or "tool"
                    )
                    status = getattr(message_obj, "status", None)
                    ok = status != "error"
                    call = str(tc_id) if tc_id else None
                    yield ToolCompleted(tool=str(name), ok=ok, call_id=call)

            if answer:
                yield OutputTextDelta(delta=answer)
            yield RunCompleted(output_text=answer)
        except Exception as exc:  # noqa: BLE001
            yield RunFailed(message=str(exc) or type(exc).__name__)
