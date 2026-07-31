"""Soothe stream mapping without requiring the soothe package."""

from __future__ import annotations

from typing import Any

import pytest

from flowjet_server.agent_runtime.events import (
    OutputTextDelta,
    Progress,
    RunCompleted,
    RunStarted,
    ToolCompleted,
    ToolStarted,
)

pytest.importorskip("langchain_core", reason="langchain-core required for message types")

from langchain_core.messages import AIMessage, ToolMessage  # noqa: E402

from flowjet_server.bridges.soothe.mapping import iter_soothe_runtime_events  # noqa: E402


class StubRunner:
    def __init__(self, chunks: list[tuple[str, str, Any]]) -> None:
        self._chunks = chunks
        self.kwargs: dict[str, Any] = {}

    async def astream(self, user_input: str, **kwargs: Any):
        self.kwargs = {"user_input": user_input, **kwargs}
        for chunk in self._chunks:
            yield chunk


@pytest.mark.asyncio
async def test_soothe_mapping_tools_and_final_answer():
    tool_call = {"name": "search", "args": {"q": "x"}, "id": "call_1", "type": "tool_call"}
    runner = StubRunner(
        [
            ("ns", "messages", (AIMessage(content="narration"), {})),
            ("ns", "messages", (AIMessage(content="", tool_calls=[tool_call]), {})),
            ("ns", "messages", (ToolMessage(content="ok", tool_call_id="call_1"), {})),
            ("ns", "messages", (AIMessage(content="Done."), {})),
        ]
    )
    events = [
        e
        async for e in iter_soothe_runtime_events(
            runner,
            run_id="resp_1",
            model="default",
            session="fj-1",
            input_text="hi",
            workspace="/tmp/ws",
        )
    ]
    assert isinstance(events[0], RunStarted)
    assert runner.kwargs["thread_id"] == "fj-1"
    assert runner.kwargs["workspace"] == "/tmp/ws"
    assert [e.tool for e in events if isinstance(e, ToolStarted)] == ["search"]
    assert [e.tool for e in events if isinstance(e, ToolCompleted)] == ["search"]
    assert any(isinstance(e, Progress) for e in events)
    completed = next(e for e in events if isinstance(e, RunCompleted))
    assert completed.output_text == "Done."
    assert all("narration" not in e.delta for e in events if isinstance(e, OutputTextDelta))
