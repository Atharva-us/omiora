"""The model interface every provider adapter implements.

Agents depend only on these types. Adapters translate them to a provider SDK and translate provider
failures into `ModelError` with a safe message. Provider response bodies, request headers, and
credentials never cross this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

Effort = Literal["low", "medium", "high", "xhigh", "max"]
ModelErrorKind = Literal[
    "not-configured",  # no credentials: actionable configuration problem, never retried
    "auth",  # credentials rejected
    "bad-request",  # the request itself is invalid (a bug or an unsupported option)
    "rate-limited",
    "timeout",
    "unavailable",  # 5xx, overload, connection failure
    "refused",  # the model declined (safety); not retried with the same input
    "truncated",  # output hit the token limit before completing
    "invalid-output",  # the provider rejected its own output against the schema; a fresh attempt may succeed
]
RETRYABLE_KINDS: frozenset[str] = frozenset({"rate-limited", "timeout", "unavailable", "truncated", "invalid-output"})


@dataclass(frozen=True)
class ModelRequest:
    system: str
    user_content: str
    output_schema: dict[str, object]  # JSON Schema for structured output
    max_output_tokens: int
    effort: Effort = "high"
    timeout_seconds: float = 300.0


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class ModelResponse:
    text: str
    provider: str
    model: str
    stop_reason: str | None
    usage: ModelUsage = field(default_factory=ModelUsage)
    request_id: str | None = None
    latency_ms: int | None = None


class ModelError(Exception):
    """Safe-to-persist failure. `message` must not contain provider bodies or credentials."""

    def __init__(
        self,
        kind: ModelErrorKind,
        message: str,
        *,
        provider: str,
        model: str,
        request_id: str | None = None,
        latency_ms: int | None = None,
        retry_after_seconds: float | None = None,
        raw_output: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind: ModelErrorKind = kind
        self.message = message
        self.provider = provider
        self.model = model
        self.request_id = request_id
        self.latency_ms = latency_ms
        # Provider-requested wait (e.g. from a 429 `retry-after` header) before trying again.
        self.retry_after_seconds = retry_after_seconds
        # The model's own rejected output, when the provider returns it (never request data or credentials).
        self.raw_output = raw_output

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE_KINDS


class ModelProvider(Protocol):
    name: str
    model: str

    @property
    def configured(self) -> bool: ...

    def generate(self, request: ModelRequest) -> ModelResponse: ...
