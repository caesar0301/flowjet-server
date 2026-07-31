"""Per-session workspace resolution."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


class WorkspaceResolver:
    """Map session (+ optional metadata.workspace) to an absolute workspace path."""

    def __init__(self, home: Path) -> None:
        self._home = Path(home).expanduser().resolve()

    @property
    def home(self) -> Path:
        return self._home

    def resolve(self, session: str, metadata: dict[str, Any] | None = None) -> Path:
        meta = metadata or {}
        override = meta.get("workspace")
        if isinstance(override, str) and override.strip():
            path = Path(override.strip()).expanduser().resolve()
            path.mkdir(parents=True, exist_ok=True)
            return path

        digest = hashlib.sha256(session.encode("utf-8")).hexdigest()[:16]
        path = self._home / "data" / "workspaces" / f"ws_{digest}"
        path.mkdir(parents=True, exist_ok=True)
        return path
