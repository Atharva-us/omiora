"""Anthropic (Claude) adapter using the official `anthropic` Python SDK (2.x).

- Structured output: `output_config.format` with a JSON Schema. The agent still validates the
  result with Pydantic, because schema-constrained output can be valid JSON yet semantically wrong.
- Thinking: Claude Opus 5.5 always uses adaptive thinking; depth is set with `output_config.effort`.
- Refusals: `stop_reason == "refusal"` is mapped to `refused`. Server-side fallback
  (`fallbacks="default"`, beta `server-side-fallback-2026-07-01`) is enabled by default and can be
  disabled with OMNIORA_ANTHROPIC_REFUSAL_FALLBACK=false.
- Transport: the SDK retries connection errors, 408/409/429/5xx up to `max_retries`; timeouts are
  per request. Errors are mapped through the SDK's typed exception classes.
"""

from __future__ import annotations

import time
from typing import Any

import anthropic

from .base import ModelError, ModelRequest, ModelResponse, ModelUsage

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        max_retries: int,
        refusal_fallback: bool,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self._refusal_fallback = refusal_fallback
        self._client = client
        if client is None and api_key:
            # The key is passed explicitly so configuration is unambiguous; it is never logged.
            self._client = anthropic.Anthropic(api_key=api_key, max_retries=max_retries)

    @property
    def configured(self) -> bool:
        return self._client is not None

    def _error(self, kind: Any, message: str, started: float, request_id: str | None = None) -> ModelError:
        latency = int((time.monotonic() - started) * 1000)
        return ModelError(
            kind, message, provider=self.name, model=self.model, request_id=request_id, latency_ms=latency
        )

    def generate(self, request: ModelRequest) -> ModelResponse:
        if self._client is None:
            raise ModelError(
                "not-configured",
                "No model provider credentials are configured. Set ANTHROPIC_API_KEY on the backend.",
                provider=self.name,
                model=self.model,
            )
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_output_tokens,
            "system": request.system,
            "messages": [{"role": "user", "content": request.user_content}],
            "output_config": {
                "effort": request.effort,
                "format": {"type": "json_schema", "schema": request.output_schema},
            },
            "timeout": request.timeout_seconds,
        }
        if self._refusal_fallback:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"

        started = time.monotonic()
        try:
            message = self._client.beta.messages.create(**params)
        except anthropic.AuthenticationError as exc:
            raise self._error(
                "auth",
                "The model provider rejected the configured credentials.",
                started,
                getattr(exc, "request_id", None),
            ) from None
        except anthropic.PermissionDeniedError as exc:
            raise self._error(
                "auth",
                "The configured credentials are not permitted to use this model.",
                started,
                getattr(exc, "request_id", None),
            ) from None
        except anthropic.NotFoundError as exc:
            raise self._error(
                "bad-request", f"The model {self.model!r} was not found.", started, getattr(exc, "request_id", None)
            ) from None
        except anthropic.RateLimitError as exc:
            raise self._error(
                "rate-limited",
                "The model provider is rate limiting requests.",
                started,
                getattr(exc, "request_id", None),
            ) from None
        except anthropic.BadRequestError as exc:
            raise self._error(
                "bad-request",
                "The model provider rejected the request as invalid.",
                started,
                getattr(exc, "request_id", None),
            ) from None
        except anthropic.APITimeoutError:
            raise self._error("timeout", "The model provider did not respond in time.", started) from None
        except anthropic.APIConnectionError:
            raise self._error("unavailable", "The model provider could not be reached.", started) from None
        except anthropic.APIStatusError as exc:
            kind = "unavailable" if exc.status_code >= 500 else "bad-request"
            raise self._error(
                kind,
                f"The model provider returned an error ({exc.status_code}).",
                started,
                getattr(exc, "request_id", None),
            ) from None

        latency_ms = int((time.monotonic() - started) * 1000)
        request_id = getattr(message, "_request_id", None)
        if message.stop_reason == "refusal":
            raise ModelError(
                "refused",
                "The model declined to produce a plan for this request.",
                provider=self.name,
                model=message.model,
                request_id=request_id,
                latency_ms=latency_ms,
            )
        if message.stop_reason in ("max_tokens", "model_context_window_exceeded"):
            raise ModelError(
                "truncated",
                "The model output was cut off before the plan was complete.",
                provider=self.name,
                model=message.model,
                request_id=request_id,
                latency_ms=latency_ms,
            )

        text = "".join(block.text for block in message.content if getattr(block, "type", None) == "text")
        usage = getattr(message, "usage", None)
        return ModelResponse(
            text=text,
            provider=self.name,
            model=message.model,  # may differ from the requested model if a fallback served the request
            stop_reason=message.stop_reason,
            usage=ModelUsage(
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
            ),
            request_id=request_id,
            latency_ms=latency_ms,
        )
