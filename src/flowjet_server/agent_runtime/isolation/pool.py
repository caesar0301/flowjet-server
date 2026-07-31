"""Persistent thread pool for isolated agent runs (RFC-002 / IG-002)."""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import logging
import queue
import threading
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from flowjet_server.agent_runtime.events import RunFailed, RuntimeEvent
from flowjet_server.agent_runtime.isolation.adapter import AdapterFactory, AgentAdapter
from flowjet_server.agent_runtime.isolation.request import IsolatedRunRequest

logger = logging.getLogger(__name__)

_POISON = object()
_WORKER_READY_TIMEOUT_SECONDS = 30.0


@dataclass(slots=True)
class PoolSettings:
    min_size: int = 2
    max_size: int = 8
    idle_timeout_seconds: float = 300.0
    reuse_runner: bool = True
    request_timeout_seconds: float = 0.0
    response_queue_maxsize: int = 200


class WorkerStatus(StrEnum):
    STARTING = "starting"
    IDLE = "idle"
    BUSY = "busy"
    DEAD = "dead"


@dataclass
class WorkerState:
    worker_id: str
    thread: threading.Thread
    request_queue: queue.Queue[Any]
    cancel_event: threading.Event
    status: WorkerStatus = WorkerStatus.STARTING
    session: str | None = None
    run_id: str | None = None
    request_id: str | None = None
    last_used: datetime = field(default_factory=datetime.now)
    ready_event: threading.Event = field(default_factory=threading.Event)

    def mark_busy(self, session: str, run_id: str, request_id: str) -> None:
        self.status = WorkerStatus.BUSY
        self.session = session
        self.run_id = run_id
        self.request_id = request_id
        self.last_used = datetime.now()

    def mark_idle(self) -> None:
        self.status = WorkerStatus.IDLE
        self.session = None
        self.run_id = None
        self.request_id = None
        self.last_used = datetime.now()
        self.cancel_event.clear()

    def is_alive(self) -> bool:
        return self.thread.is_alive()


class _ResponseBridge:
    """Push messages from a worker thread onto an asyncio.Queue on the main loop."""

    def __init__(self, loop: asyncio.AbstractEventLoop, response_queue: asyncio.Queue[Any]) -> None:
        self._loop = loop
        self._queue = response_queue

    def emit(self, msg_type: str, payload: Any = None) -> None:
        def _put() -> None:
            try:
                self._queue.put_nowait((msg_type, payload))
            except asyncio.QueueFull:
                logger.warning("isolation ThreadPool: response queue full; dropping %s", msg_type)

        self._loop.call_soon_threadsafe(_put)


def _worker_main(
    worker_id: str,
    request_queue: queue.Queue[Any],
    cancel_event: threading.Event,
    ready_event: threading.Event,
    adapter_factory: AdapterFactory,
    reuse_runner: bool,
    request_timeout_seconds: float,
) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    adapter: AgentAdapter | None = None

    def ensure_adapter() -> AgentAdapter:
        nonlocal adapter
        if adapter is None:
            adapter = adapter_factory()
        return adapter

    async def execute(req: IsolatedRunRequest, bridge: _ResponseBridge) -> None:
        nonlocal adapter
        cancel_event.clear()
        runner = ensure_adapter()
        try:
            timeout = request_timeout_seconds if request_timeout_seconds > 0 else None

            async def _stream() -> None:
                async for event in runner.astream(req):
                    if cancel_event.is_set():
                        bridge.emit("cancelled")
                        return
                    bridge.emit("event", event)
                bridge.emit("done")

            # Do not inherit context variables from a previous worker-loop task.
            # Agent libraries use ContextVar for workspace, model overrides,
            # logging identity, and per-turn tool registries. A fresh Context
            # makes request isolation explicit even when an adapter is reused.
            stream_task = asyncio.create_task(_stream(), context=contextvars.Context())

            async def _watch_cancel() -> None:
                while not stream_task.done():
                    if cancel_event.is_set():
                        stream_task.cancel()
                        return
                    await asyncio.sleep(0.02)

            watcher = asyncio.create_task(_watch_cancel())
            try:
                if timeout is not None:
                    async with asyncio.timeout(timeout):
                        await stream_task
                else:
                    await stream_task
            except asyncio.CancelledError:
                if cancel_event.is_set():
                    bridge.emit("cancelled")
                else:
                    raise
            finally:
                watcher.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await watcher
        except TimeoutError:
            bridge.emit("error", RuntimeError(f"Request exceeded {timeout}s timeout"))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Worker %s failed session=%s", worker_id, req.session)
            bridge.emit("error", exc)
        finally:
            try:
                if reuse_runner:
                    runner.prepare_for_request()
                else:
                    await runner.cleanup()
                    adapter = None
            except Exception:  # noqa: BLE001
                logger.debug("Worker %s prepare/cleanup failed", worker_id, exc_info=True)

    ready_event.set()
    try:
        while True:
            item = request_queue.get()
            if item is _POISON:
                break
            _kind, _request_id, req, bridge = item
            assert isinstance(req, IsolatedRunRequest)
            assert isinstance(bridge, _ResponseBridge)
            try:
                loop.run_until_complete(execute(req, bridge))
            except Exception as exc:  # noqa: BLE001
                bridge.emit("error", exc)
            finally:
                bridge.emit("ready")
    finally:
        if adapter is not None:
            try:
                loop.run_until_complete(adapter.cleanup())
            except Exception:  # noqa: BLE001
                pass
        loop.close()


class ThreadPool:
    """Shared pool of worker threads for IsolatedRunRequest execution."""

    def __init__(
        self,
        adapter_factory: AdapterFactory,
        settings: PoolSettings | None = None,
    ) -> None:
        self._factory = adapter_factory
        self._settings = settings or PoolSettings()
        if self._settings.min_size < 1:
            raise ValueError("min_size must be >= 1")
        if self._settings.max_size < self._settings.min_size:
            raise ValueError("max_size must be >= min_size")

        self._workers: dict[str, WorkerState] = {}
        self._session_to_worker: dict[str, str] = {}
        self._run_to_worker: dict[str, str] = {}
        self._pending: dict[str, asyncio.Queue[Any]] = {}
        self._lock = asyncio.Lock()
        self._worker_available: asyncio.Condition | None = None
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self._running = False
        self._session_waiters: dict[str, asyncio.Condition] = {}

    @property
    def settings(self) -> PoolSettings:
        return self._settings

    async def start(self) -> None:
        async with self._lock:
            if self._running:
                return
            self._main_loop = asyncio.get_running_loop()
            self._worker_available = asyncio.Condition()
            self._running = True
            for _ in range(self._settings.min_size):
                self._spawn_worker_unlocked()

    def _spawn_worker_unlocked(self) -> WorkerState:
        worker_id = f"w_{uuid.uuid4().hex[:8]}"
        request_queue: queue.Queue[Any] = queue.Queue()
        cancel_event = threading.Event()
        ready_event = threading.Event()
        thread = threading.Thread(
            target=_worker_main,
            name=f"flowjet-pool-{worker_id}",
            args=(
                worker_id,
                request_queue,
                cancel_event,
                ready_event,
                self._factory,
                self._settings.reuse_runner,
                self._settings.request_timeout_seconds,
            ),
            daemon=True,
        )
        state = WorkerState(
            worker_id=worker_id,
            thread=thread,
            request_queue=request_queue,
            cancel_event=cancel_event,
            ready_event=ready_event,
        )
        self._workers[worker_id] = state
        thread.start()
        if not ready_event.wait(timeout=_WORKER_READY_TIMEOUT_SECONDS):
            state.status = WorkerStatus.DEAD
            raise RuntimeError(f"Worker {worker_id} failed to become ready")
        state.status = WorkerStatus.IDLE
        return state

    async def shutdown(self, timeout: float = 5.0) -> None:
        async with self._lock:
            self._running = False
            workers = list(self._workers.values())
            self._workers.clear()
            self._session_to_worker.clear()
            self._run_to_worker.clear()
        for w in workers:
            w.request_queue.put(_POISON)
            w.cancel_event.set()
        for w in workers:
            w.thread.join(timeout=timeout)

    def _session_condition(self, session: str) -> asyncio.Condition:
        cond = self._session_waiters.get(session)
        if cond is None:
            cond = asyncio.Condition()
            self._session_waiters[session] = cond
        return cond

    async def await_session_dispatchable(self, session: str) -> None:
        """Wait until no worker is busy with this session."""
        cond = self._session_condition(session)
        async with cond:
            while session in self._session_to_worker:
                await cond.wait()

    async def _acquire_idle_worker(self, session: str, run_id: str, request_id: str) -> WorkerState:
        assert self._worker_available is not None
        while True:
            async with self._lock:
                for w in self._workers.values():
                    if w.status == WorkerStatus.IDLE and w.is_alive():
                        w.mark_busy(session, run_id, request_id)
                        self._session_to_worker[session] = w.worker_id
                        self._run_to_worker[run_id] = w.worker_id
                        return w
                alive = sum(1 for w in self._workers.values() if w.is_alive())
                if alive < self._settings.max_size:
                    w = self._spawn_worker_unlocked()
                    w.mark_busy(session, run_id, request_id)
                    self._session_to_worker[session] = w.worker_id
                    self._run_to_worker[run_id] = w.worker_id
                    return w
            async with self._worker_available:
                await self._worker_available.wait()

    async def submit(self, request: IsolatedRunRequest) -> AsyncIterator[RuntimeEvent]:
        if not self._running:
            await self.start()
        assert self._main_loop is not None
        assert self._worker_available is not None

        request_id = request.request_id or uuid.uuid4().hex[:16]
        req = IsolatedRunRequest(
            run_id=request.run_id,
            session=request.session,
            input_text=request.input_text,
            model=request.model,
            workspace=request.workspace,
            thread_id=request.thread_id,
            metadata=request.metadata,
            request_id=request_id,
        )

        await self.await_session_dispatchable(req.session)

        response_queue: asyncio.Queue[Any] = asyncio.Queue(
            maxsize=self._settings.response_queue_maxsize
        )
        worker = await self._acquire_idle_worker(req.session, req.run_id, request_id)
        bridge = _ResponseBridge(self._main_loop, response_queue)

        async with self._lock:
            self._pending[request_id] = response_queue

        worker.request_queue.put(("request", request_id, req, bridge))

        terminal_received = False
        worker_ready = False
        try:
            while True:
                msg_type, payload = await response_queue.get()
                if msg_type == "event":
                    if not terminal_received:
                        yield payload  # type: ignore[misc]
                elif msg_type == "done":
                    terminal_received = True
                elif msg_type == "cancelled":
                    if not terminal_received:
                        yield RunFailed(message="cancelled", code="cancelled")
                    terminal_received = True
                elif msg_type == "error":
                    if not terminal_received:
                        exc = payload
                        message = str(exc) if exc else "worker error"
                        yield RunFailed(message=message, code="worker_error")
                    terminal_received = True
                elif msg_type == "ready":
                    worker_ready = True
                    if terminal_received:
                        break
        finally:
            # A client may stop consuming after any event (for example an SSE
            # disconnect). Cancel that turn and hold the worker reservation
            # until its adapter has completed cleanup/prepare. Releasing it
            # earlier would let the pool queue another request against a
            # still-active worker-local runner.
            if not worker_ready:
                if not terminal_received:
                    worker.cancel_event.set()
                while not worker_ready:
                    msg_type, _payload = await response_queue.get()
                    worker_ready = msg_type == "ready"

            async with self._lock:
                self._pending.pop(request_id, None)
                self._run_to_worker.pop(req.run_id, None)
                self._session_to_worker.pop(req.session, None)
                if worker.worker_id in self._workers:
                    worker.mark_idle()
            cond = self._session_condition(req.session)
            async with cond:
                cond.notify_all()
            async with self._worker_available:
                self._worker_available.notify_all()

    def cancel_run(self, run_id: str) -> bool:
        worker_id = self._run_to_worker.get(run_id)
        if worker_id is None:
            return False
        worker = self._workers.get(worker_id)
        if worker is None:
            return False
        worker.cancel_event.set()
        return True

    def cancel_session(self, session: str) -> bool:
        worker_id = self._session_to_worker.get(session)
        if worker_id is None:
            return False
        worker = self._workers.get(worker_id)
        if worker is None:
            return False
        worker.cancel_event.set()
        return True
