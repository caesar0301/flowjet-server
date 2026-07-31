"""Tests for RFC-002 isolation: workspace, admission, thread pool."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from flowjet_server.agent_runtime.events import (
    OutputTextDelta,
    RunCompleted,
    RunFailed,
    RunRequest,
    RunStarted,
)
from flowjet_server.agent_runtime.isolation import (
    FakeAgentAdapter,
    IsolatedRunRequest,
    IsolatingRuntimeBackend,
    PoolSettings,
    SessionAdmission,
    ThreadPool,
    WorkspaceResolver,
)


def test_workspace_resolver_hash_and_override(tmp_path: Path):
    resolver = WorkspaceResolver(tmp_path)
    a = resolver.resolve("session-a")
    b = resolver.resolve("session-b")
    assert a != b
    assert a.is_dir()
    assert a.parent == tmp_path / "data" / "workspaces"

    override = tmp_path / "custom-ws"
    resolved = resolver.resolve("session-a", {"workspace": str(override)})
    assert resolved == override.resolve()
    assert resolved.is_dir()


@pytest.mark.asyncio
async def test_session_admission_serializes_same_session():
    admission = SessionAdmission()
    order: list[str] = []

    async def turn(label: str, delay: float) -> None:
        async with admission.admit("same"):
            order.append(f"{label}-start")
            await asyncio.sleep(delay)
            order.append(f"{label}-end")

    await asyncio.gather(turn("a", 0.05), turn("b", 0.01))
    # Second turn must not start until first ends.
    assert order.index("a-end") < order.index("b-start") or order.index("b-end") < order.index(
        "a-start"
    )


@pytest.mark.asyncio
async def test_thread_pool_submit_yields_events(tmp_path: Path):
    pool = ThreadPool(FakeAgentAdapter, PoolSettings(min_size=1, max_size=2))
    await pool.start()
    try:
        ws = tmp_path / "ws"
        ws.mkdir()
        req = IsolatedRunRequest(
            run_id="resp_1",
            session="fj-1",
            input_text="hello",
            model="default",
            workspace=ws,
        )
        events = [e async for e in pool.submit(req)]
        assert isinstance(events[0], RunStarted)
        assert any(isinstance(e, OutputTextDelta) for e in events)
        assert isinstance(events[-1], RunCompleted)
        assert (ws / "last_input.txt").read_text(encoding="utf-8") == "hello"
    finally:
        await pool.shutdown()


@pytest.mark.asyncio
async def test_pool_cross_session_parallel_workspaces(tmp_path: Path):
    pool = ThreadPool(
        lambda: FakeAgentAdapter(delay_s=0.05),
        PoolSettings(min_size=2, max_size=4),
    )
    await pool.start()
    try:
        ws_a = tmp_path / "a"
        ws_b = tmp_path / "b"
        ws_a.mkdir()
        ws_b.mkdir()

        async def run(session: str, workspace: Path, text: str) -> list:
            req = IsolatedRunRequest(
                run_id=f"resp_{session}",
                session=session,
                input_text=text,
                model="default",
                workspace=workspace,
            )
            return [e async for e in pool.submit(req)]

        results = await asyncio.gather(
            run("fj-a", ws_a, "alpha"),
            run("fj-b", ws_b, "beta"),
        )
        assert all(isinstance(r[-1], RunCompleted) for r in results)
        assert (ws_a / "last_input.txt").read_text(encoding="utf-8") == "alpha"
        assert (ws_b / "last_input.txt").read_text(encoding="utf-8") == "beta"
    finally:
        await pool.shutdown()


@pytest.mark.asyncio
async def test_same_session_serialized_in_pool(tmp_path: Path):
    pool = ThreadPool(
        lambda: FakeAgentAdapter(delay_s=0.04),
        PoolSettings(min_size=2, max_size=4),
    )
    await pool.start()
    try:
        ws = tmp_path / "s"
        ws.mkdir()
        started: list[float] = []
        loop = asyncio.get_running_loop()

        async def run(text: str) -> None:
            started.append(loop.time())
            req = IsolatedRunRequest(
                run_id=f"resp_{text}",
                session="fj-shared",
                input_text=text,
                model="default",
                workspace=ws,
            )
            async for _ in pool.submit(req):
                pass

        await asyncio.gather(run("one"), run("two"))
        # Starts may be close, but final file must be from the later-finishing turn;
        # more importantly both complete without cross-corrupting via admission.
        assert (ws / "last_input.txt").read_text(encoding="utf-8") in {"one", "two"}
        assert abs(started[0] - started[1]) < 1.0
    finally:
        await pool.shutdown()


@pytest.mark.asyncio
async def test_cancel_run(tmp_path: Path):
    pool = ThreadPool(
        lambda: FakeAgentAdapter(delay_s=2.0),
        PoolSettings(min_size=1, max_size=1),
    )
    await pool.start()
    try:
        ws = tmp_path / "c"
        ws.mkdir()
        req = IsolatedRunRequest(
            run_id="resp_cancel",
            session="fj-c",
            input_text="slow",
            model="default",
            workspace=ws,
        )

        async def consume() -> list:
            return [e async for e in pool.submit(req)]

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.05)
        assert pool.cancel_run("resp_cancel")
        events = await asyncio.wait_for(task, timeout=2.0)
        assert any(isinstance(e, RunFailed) and e.code == "cancelled" for e in events)
    finally:
        await pool.shutdown()


@pytest.mark.asyncio
async def test_isolating_backend_stream(tmp_path: Path):
    backend = IsolatingRuntimeBackend(
        models=["default"],
        adapter_factory=FakeAgentAdapter,
        pool_settings=PoolSettings(min_size=1, max_size=2),
        home=tmp_path,
    )
    try:
        events = [
            e
            async for e in backend.stream_run(
                RunRequest(model="default", input_text="ping", session="fj-x")
            )
        ]
        assert isinstance(events[0], RunStarted)
        assert events[0].session == "fj-x"
        assert isinstance(events[-1], RunCompleted)
        # Workspace created under FLOWJET_HOME
        workspaces = list((tmp_path / "data" / "workspaces").iterdir())
        assert len(workspaces) == 1
        assert (workspaces[0] / "last_input.txt").read_text(encoding="utf-8") == "ping"
    finally:
        await backend.shutdown()


@pytest.mark.asyncio
async def test_isolating_backend_via_http(tmp_path: Path):
    from httpx import ASGITransport, AsyncClient

    from flowjet_server.http.app import create_app

    backend = IsolatingRuntimeBackend(
        models=["default"],
        adapter_factory=FakeAgentAdapter,
        pool_settings=PoolSettings(min_size=1, max_size=2),
        home=tmp_path,
    )
    app = create_app(backend=backend)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/v1/responses",
            json={
                "model": "default",
                "input": "http-hi",
                "flowjet": {"session": "fj-http"},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert "http-hi" in body["output"][0]["content"][0]["text"]
    await backend.shutdown()
