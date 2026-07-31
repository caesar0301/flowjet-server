"""Map SootheRunner StreamChunk tuples to Agent Runtime events."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from flowjet_server.agent_runtime.events import (
    InterruptWaiting,
    OutputTextDelta,
    Progress,
    RunCompleted,
    RunFailed,
    RunStarted,
    RuntimeEvent,
    ToolCompleted,
    ToolStarted,
)
from flowjet_server.bridges.nano.mapping import ai_text, map_custom


async def iter_soothe_runtime_events(
    runner: Any,
    *,
    run_id: str,
    model: str,
    session: str,
    input_text: str,
    workspace: str,
    thread_id: str | None = None,
) -> AsyncIterator[RuntimeEvent]:
    """Drive ``SootheRunner.astream`` and yield sanitized runtime events."""
    try:
        from langchain_core.messages import AIMessage, ToolMessage
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("langchain-core is required for the soothe bridge") from exc

    tid = thread_id or session
    yield RunStarted(run_id=run_id, model=model, session=session)

    answer = ""
    composing = False
    open_tools: dict[str, str] = {}

    try:
        async for chunk in runner.astream(
            input_text,
            thread_id=tid,
            workspace=workspace,
        ):
            if not isinstance(chunk, tuple) or len(chunk) != 3:
                continue
            _ns, mode, data = chunk

            if mode == "custom" and isinstance(data, dict):
                mapped = map_custom(data)
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
                text = ai_text(message_obj)
                if text:
                    if text.startswith(answer):
                        delta = text[len(answer) :]
                    elif answer.startswith(text):
                        delta = ""
                    else:
                        delta = text
                    if delta:
                        answer = text if text.startswith(answer) else answer + delta
                        if not composing:
                            composing = True
                            yield Progress(stage="Working", message="Composing response…")

            elif isinstance(message_obj, ToolMessage):
                tc_id = getattr(message_obj, "tool_call_id", None)
                name = (
                    open_tools.pop(str(tc_id), None) or getattr(message_obj, "name", None) or "tool"
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
