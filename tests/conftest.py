"""Shared test helpers and live-server fixtures for OpenAI SDK tests."""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import uvicorn
from openai import OpenAI

from flowjet_server.agent_runtime.fake import FakeRuntimeBackend
from flowjet_server.config import Settings
from flowjet_server.http.app import create_app


def parse_sse(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        data_line = None
        for line in block.splitlines():
            if line.startswith("data: "):
                data_line = line[6:]
        if data_line:
            events.append(json.loads(data_line))
    return events


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class LiveServer:
    def __init__(self, app: object, host: str = "127.0.0.1") -> None:
        self.host = host
        self.port = _free_port()
        self.config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="error",
            access_log=False,
        )
        self.server = uvicorn.Server(self.config)
        self._thread = threading.Thread(target=self.server.run, name="uvicorn-test", daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"

    @property
    def root_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self, timeout: float = 10.0) -> None:
        self._thread.start()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.server.started:
                try:
                    r = httpx.get(f"{self.root_url}/health", timeout=0.5)
                    if r.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
            time.sleep(0.05)
        raise RuntimeError("uvicorn test server failed to start")

    def stop(self) -> None:
        self.server.should_exit = True
        self._thread.join(timeout=5)


@pytest.fixture
def live_server() -> Iterator[LiveServer]:
    app = create_app(
        settings=Settings(api_key=None, backend="fake", models="default,researcher"),
        backend=FakeRuntimeBackend(models=["default", "researcher"]),
    )
    server = LiveServer(app)
    server.start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def openai_client(live_server: LiveServer) -> OpenAI:
    return OpenAI(api_key="local-test-key", base_url=live_server.base_url)


@pytest.fixture
def authed_live_server() -> Iterator[tuple[LiveServer, str]]:
    api_key = "test-secret-key"
    app = create_app(
        settings=Settings(api_key=api_key, backend="fake", models="default"),
        backend=FakeRuntimeBackend(models=["default"]),
    )
    server = LiveServer(app)
    server.start()
    try:
        yield server, api_key
    finally:
        server.stop()
