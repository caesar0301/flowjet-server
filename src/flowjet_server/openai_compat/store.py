"""In-process Response run store (Phase 1)."""

from __future__ import annotations

from typing import Any


class InMemoryRunStore:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    def put(self, response_id: str, body: dict[str, Any]) -> None:
        self._items[response_id] = body

    def get(self, response_id: str) -> dict[str, Any] | None:
        return self._items.get(response_id)

    def delete(self, response_id: str) -> bool:
        return self._items.pop(response_id, None) is not None
