"""Agent Runtime Protocol event types (RFC-001 §8)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RunStarted:
    run_id: str
    model: str
    session: str | None = None


@dataclass(frozen=True, slots=True)
class Progress:
    stage: str
    message: str


@dataclass(frozen=True, slots=True)
class ToolStarted:
    tool: str
    call_id: str | None = None


@dataclass(frozen=True, slots=True)
class ToolCompleted:
    tool: str
    ok: bool
    call_id: str | None = None
    duration_ms: int | None = None


@dataclass(frozen=True, slots=True)
class OutputTextDelta:
    delta: str


@dataclass(frozen=True, slots=True)
class InterruptWaiting:
    message: str | None = None


@dataclass(frozen=True, slots=True)
class UsageInfo:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True, slots=True)
class RunCompleted:
    output_text: str
    usage: UsageInfo | None = None


@dataclass(frozen=True, slots=True)
class RunFailed:
    message: str
    code: str | None = None


@dataclass(frozen=True, slots=True)
class RunRequest:
    model: str
    input_text: str
    session: str | None = None
    metadata: dict[str, Any] | None = None
    run_id: str | None = None


@dataclass(frozen=True, slots=True)
class ModelInfo:
    id: str
    owned_by: str = "flowjet"


RuntimeEvent = (
    RunStarted
    | Progress
    | ToolStarted
    | ToolCompleted
    | OutputTextDelta
    | InterruptWaiting
    | RunCompleted
    | RunFailed
)
