"""Groq adapter using the official `groq` Python SDK (chat completions API).

- Structured output: `response_format={"type": "json_schema", ...}`, strict on models Groq documents as
  supporting strict mode (https://console.groq.com/docs/structured-outputs). Other models fall back to
  best-effort schema mode or JSON mode, in that order. The agent validates every result either way.
- Reasoning: gpt-oss models take `reasoning_effort` low/medium/high. Omniora's `xhigh`/`max` map to
  `high`. Reasoning text is excluded from the response (`include_reasoning=False`); it is not used.
- Transport: the SDK retries connection errors, 408/409/429/5xx up to `max_retries`, honouring
  `retry-after` up to 60 s. Errors are mapped through the SDK's typed exceptions to safe messages.
  Provider bodies and the API key never reach `ModelError`.
"""

from __future__ import annotations

import json
import time
from typing import Any

import groq

from .base import Effort, ModelError, ModelErrorKind, ModelRequest, ModelResponse, ModelUsage

# From Groq's structured-outputs documentation.
STRICT_SCHEMA_MODELS = frozenset(
    {"openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b", "meta-models/muse-spark-open"}
)
BEST_EFFORT_SCHEMA_MODELS = STRICT_SCHEMA_MODELS | {"openai/gpt-oss-safeguard-20b"}
GPT_OSS_PREFIX = "openai/gpt-oss"

_EFFORT: dict[Effort, str] = {"low": "low", "medium": "medium", "high": "high", "xhigh": "high", "max": "high"}


def _error_code(exc: groq.APIStatusError) -> str:
    """The provider's machine-readable error code, if any (never its message)."""
    body = exc.body if isinstance(exc.body, dict) else {}
    error = body.get("error", body)
    return str(error.get("code") or error.get("type") or "") if isinstance(error, dict) else ""


def _retry_after(exc: groq.APIStatusError) -> float | None:
    value = exc.response.headers.get("retry-after") if exc.response is not None else None
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


class GroqProvider:
    name = "groq"

    def __init__(self, *, api_key: str | None, model: str, max_retries: int, client: Any | None = None) -> None:
        self.model = model
        self._client = client
        if client is None and api_key:
            # The key is passed explicitly so configuration is unambiguous; it is never logged.
            self._client = groq.Groq(api_key=api_key, max_retries=max_retries)

    @property
    def configured(self) -> bool:
        return self._client is not None

    def _response_format(self, schema: dict[str, object]) -> dict[str, Any]:
        if self.model in BEST_EFFORT_SCHEMA_MODELS:
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": "project_plan",
                    "schema": schema,
                    "strict": self.model in STRICT_SCHEMA_MODELS,
                },
            }
        return {"type": "json_object"}

    def _params(self, request: ModelRequest) -> dict[str, Any]:
        user_content = request.user_content
        if self.model not in BEST_EFFORT_SCHEMA_MODELS:
            # JSON mode does not enforce a schema, so the schema travels in the prompt instead.
            user_content += "\n<output_json_schema>\n" + json.dumps(request.output_schema) + "\n</output_json_schema>"
        params: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": user_content},
            ],
            "response_format": self._response_format(request.output_schema),
            "max_completion_tokens": request.max_output_tokens,
            "timeout": request.timeout_seconds,
        }
        if self.model.startswith(GPT_OSS_PREFIX):
            params["reasoning_effort"] = _EFFORT[request.effort]
            params["include_reasoning"] = False
        return params

    def _error(
        self, kind: ModelErrorKind, message: str, started: float, *, retry_after: float | None = None
    ) -> ModelError:
        latency = int((time.monotonic() - started) * 1000)
        return ModelError(
            kind, message, provider=self.name, model=self.model, latency_ms=latency, retry_after_seconds=retry_after
        )

    def generate(self, request: ModelRequest) -> ModelResponse:
        if self._client is None:
            raise ModelError(
                "not-configured",
                "No Groq credentials are configured. Set GROQ_API_KEY on the backend.",
                provider=self.name,
                model=self.model,
            )
        started = time.monotonic()
        try:
            completion = self._client.chat.completions.create(**self._params(request))
        except groq.AuthenticationError:
            raise self._error("auth", "Groq rejected the configured credentials.", started) from None
        except groq.PermissionDeniedError:
            raise self._error("auth", "The configured Groq credentials may not use this model.", started) from None
        except groq.NotFoundError:
            raise self._error("bad-request", f"The Groq model {self.model!r} was not found.", started) from None
        except groq.RateLimitError as exc:
            if _error_code(exc) == "request_too_large" or "too large" in str(exc.message).lower():
                raise self._error(
                    "bad-request",
                    "The request exceeds Groq's per-minute token limit for this account. "
                    "Lower OMNIORA_PM_MAX_OUTPUT_TOKENS or raise the account's limits.",
                    started,
                ) from None
            raise self._error(
                "rate-limited", "Groq is rate limiting requests.", started, retry_after=_retry_after(exc)
            ) from None
        except groq.BadRequestError as exc:
            if _error_code(exc) == "json_validate_failed":
                raise self._error(
                    "invalid-output", "The model's output did not match the required schema.", started
                ) from None
            raise self._error("bad-request", "Groq rejected the request as invalid.", started) from None
        except groq.APITimeoutError:
            raise self._error("timeout", "Groq did not respond in time.", started) from None
        except groq.APIConnectionError:
            raise self._error("unavailable", "Groq could not be reached.", started) from None
        except groq.APIStatusError as exc:
            if exc.status_code == 413:
                raise self._error(
                    "bad-request",
                    "The request is too large for Groq. Lower OMNIORA_PM_MAX_OUTPUT_TOKENS.",
                    started,
                ) from None
            kind: ModelErrorKind = "unavailable" if exc.status_code >= 500 else "bad-request"
            raise self._error(kind, f"Groq returned an error ({exc.status_code}).", started) from None

        latency_ms = int((time.monotonic() - started) * 1000)
        request_id = getattr(completion, "_request_id", None) or getattr(completion, "id", None)
        choice = completion.choices[0] if completion.choices else None
        if choice is None:
            raise ModelError(
                "unavailable",
                "Groq returned no choices.",
                provider=self.name,
                model=self.model,
                request_id=request_id,
                latency_ms=latency_ms,
            )
        if choice.finish_reason == "length":
            raise ModelError(
                "truncated",
                "The model output was cut off before the plan was complete.",
                provider=self.name,
                model=completion.model or self.model,
                request_id=request_id,
                latency_ms=latency_ms,
            )
        usage = getattr(completion, "usage", None)
        return ModelResponse(
            text=choice.message.content or "",
            provider=self.name,
            model=completion.model or self.model,
            stop_reason=choice.finish_reason,
            usage=ModelUsage(
                input_tokens=getattr(usage, "prompt_tokens", None),
                output_tokens=getattr(usage, "completion_tokens", None),
            ),
            request_id=request_id,
            latency_ms=latency_ms,
        )
