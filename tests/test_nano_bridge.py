"""Nano bridge translation of soothe-nano streams into Agent Runtime events."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from flowjet_server.agent_runtime.events import (
    OutputTextDelta,
    Progress,
    RunCompleted,
    RunFailed,
    RunRequest,
    RunStarted,
    ToolCompleted,
    ToolStarted,
)

pytest.importorskip("langchain_core", reason="nano extra not installed")

from langchain_core.messages import AIMessage, ToolMessage  # noqa: E402

from flowjet_server.agent_runtime.isolation.request import IsolatedRunRequest  # noqa: E402
from flowjet_server.bridges.nano.adapter import NanoAgentAdapter  # noqa: E402
from flowjet_server.bridges.nano.backend import NanoRuntimeBackend  # noqa: E402


class StubAgent:
    """Replays a canned soothe-nano ``astream`` transcript."""

    def __init__(self, chunks: list[tuple[str, str, Any]]) -> None:
        self._chunks = chunks

    async def astream(self, _input, **_kwargs):
        for chunk in self._chunks:
            yield chunk


def message_chunk(message: Any) -> tuple[str, str, Any]:
    return ("ns", "messages", (message, {}))


async def collect(chunks: list[tuple[str, str, Any]]) -> list[Any]:
    backend = NanoRuntimeBackend(agent=StubAgent(chunks))
    request = RunRequest(model="default", input_text="hi")
    return [event async for event in backend.stream_run(request)]


@pytest.mark.asyncio
async def test_token_chunks_produce_one_progress_milestone():
    events = await collect(
        [
            message_chunk(AIMessage(content="Hello")),
            message_chunk(AIMessage(content=" streaming")),
            message_chunk(AIMessage(content=" world")),
        ]
    )

    progress = [e for e in events if isinstance(e, Progress)]
    assert len(progress) == 1, "each token chunk must not become its own progress event"

    completed = [e for e in events if isinstance(e, RunCompleted)]
    assert [e.output_text for e in completed] == ["Hello streaming world"]
    assert [e.delta for e in events if isinstance(e, OutputTextDelta)] == ["Hello streaming world"]


@pytest.mark.asyncio
async def test_progress_never_carries_answer_text():
    events = await collect([message_chunk(AIMessage(content="The secret is 42."))])

    for event in events:
        if isinstance(event, Progress):
            assert "secret" not in event.message
            assert "42" not in event.message


@pytest.mark.asyncio
async def test_pre_tool_narration_is_dropped_and_tools_are_summarised():
    tool_call = {"name": "search", "args": {"q": "x"}, "id": "call_1", "type": "tool_call"}
    events = await collect(
        [
            message_chunk(AIMessage(content="Let me look that up.")),
            message_chunk(AIMessage(content="", tool_calls=[tool_call])),
            message_chunk(ToolMessage(content="result", tool_call_id="call_1")),
            message_chunk(AIMessage(content="Final answer.")),
        ]
    )

    assert [e.tool for e in events if isinstance(e, ToolStarted)] == ["search"]
    assert [(e.tool, e.ok) for e in events if isinstance(e, ToolCompleted)] == [("search", True)]

    completed = next(e for e in events if isinstance(e, RunCompleted))
    assert completed.output_text == "Final answer."
    assert "Let me look that up." not in completed.output_text

    # The narration is superseded by the tool call, so it must not reach the client.
    assert all("look that up" not in e.delta for e in events if isinstance(e, OutputTextDelta))


@pytest.mark.asyncio
async def test_run_starts_before_any_output():
    events = await collect([message_chunk(AIMessage(content="ok"))])
    assert isinstance(events[0], RunStarted)


class FailingAgent:
    async def astream(self, _input, **_kwargs):
        raise RuntimeError("broken graph")
        yield  # pragma: no cover


class BlockingAgent:
    async def astream(self, _input, **_kwargs):
        await asyncio.sleep(10)
        yield message_chunk(AIMessage(content="too late"))


def isolated_request() -> IsolatedRunRequest:
    return IsolatedRunRequest(
        run_id="resp_isolated",
        session="fj-isolated",
        input_text="hi",
        model="default",
        workspace=Path("/tmp/flowjet-test-workspace"),
    )


@pytest.mark.asyncio
async def test_nano_adapter_recycles_agent_after_failed_turn():
    agents = [
        FailingAgent(),
        StubAgent([message_chunk(AIMessage(content="recovered"))]),
    ]
    adapter = NanoAgentAdapter(agent_factory=lambda: agents.pop(0))

    failed = [event async for event in adapter.astream(isolated_request())]
    assert any(isinstance(event, RunFailed) for event in failed)
    assert adapter.generation == 1

    adapter.prepare_for_request()
    recovered = [event async for event in adapter.astream(isolated_request())]
    assert any(
        isinstance(event, RunCompleted) and event.output_text == "recovered" for event in recovered
    )
    assert adapter.generation == 2


@pytest.mark.asyncio
async def test_nano_adapter_reuses_agent_after_clean_turn():
    agent = StubAgent([message_chunk(AIMessage(content="ok"))])
    adapter = NanoAgentAdapter(agent_factory=lambda: agent)

    for _ in range(2):
        events = [event async for event in adapter.astream(isolated_request())]
        assert isinstance(events[-1], RunCompleted)
        adapter.prepare_for_request()

    assert adapter.generation == 1


@pytest.mark.asyncio
async def test_nano_adapter_recycles_agent_after_cancelled_turn():
    agents = [
        BlockingAgent(),
        StubAgent([message_chunk(AIMessage(content="recovered"))]),
    ]
    adapter = NanoAgentAdapter(agent_factory=lambda: agents.pop(0))

    async def consume() -> list[Any]:
        return [event async for event in adapter.astream(isolated_request())]

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    adapter.prepare_for_request()
    recovered = [event async for event in adapter.astream(isolated_request())]
    assert isinstance(recovered[-1], RunCompleted)
    assert adapter.generation == 2
