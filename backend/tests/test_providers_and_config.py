"""Anthropic adapter (with a fake SDK client), configuration guards, redaction, and rate limiting."""

from __future__ import annotations

import inspect
import json
import logging
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from pydantic import ValidationError

from omniora_api.config import Settings
from omniora_api.llm.anthropic_provider import FALLBACK_BETA, AnthropicProvider
from omniora_api.llm.base import ModelError, ModelRequest
from omniora_api.logging_setup import JsonFormatter, redact
from omniora_api.security.rate_limit import SlidingWindowLimiter

REQUEST = ModelRequest(system="sys", user_content="data", output_schema={"type": "object"}, max_output_tokens=4000)


class FakeMessages:
    def __init__(self, result) -> None:
        self.result = result
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def fake_client(result) -> SimpleNamespace:
    messages = FakeMessages(result)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages), messages_impl=messages)


def message(stop_reason: str = "end_turn", text: str = '{"ok": true}', model: str = "claude-opus-5-5"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        model=model,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=12, output_tokens=34),
        _request_id="req_123",
    )


def provider(result, *, fallback: bool = True) -> tuple[AnthropicProvider, FakeMessages]:
    client = fake_client(result)
    return AnthropicProvider(
        api_key=None, model="claude-opus-5-5", max_retries=2, refusal_fallback=fallback, client=client
    ), client.messages_impl


def status_error(cls, status: int):
    response = httpx2.Response(status, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))
    return cls("secret-bearing provider body should never leak", response=response, body={"secret": "x"})


class TestAnthropicProvider:
    def test_builds_a_structured_output_request_accepted_by_the_sdk(self) -> None:
        adapter, messages = provider(message())
        response = adapter.generate(REQUEST)
        call = messages.calls[0]
        assert call["output_config"] == {
            "effort": "high",
            "format": {"type": "json_schema", "schema": {"type": "object"}},
        }
        assert call["fallbacks"] == "default" and call["betas"] == [FALLBACK_BETA]
        assert call["max_tokens"] == 4000 and call["timeout"] == 300.0
        # Every parameter we send must exist on the installed SDK's create() signature.
        signature = inspect.signature(anthropic.Anthropic(api_key="test").beta.messages.create)
        assert set(call) <= set(signature.parameters)
        assert response.text == '{"ok": true}' and response.usage.output_tokens == 34
        assert response.request_id == "req_123"

    def test_fallback_can_be_disabled(self) -> None:
        adapter, messages = provider(message(), fallback=False)
        adapter.generate(REQUEST)
        assert "fallbacks" not in messages.calls[0] and "betas" not in messages.calls[0]

    @pytest.mark.parametrize(("stop_reason", "kind"), [("refusal", "refused"), ("max_tokens", "truncated")])
    def test_maps_stop_reasons(self, stop_reason: str, kind: str) -> None:
        adapter, _ = provider(message(stop_reason=stop_reason))
        with pytest.raises(ModelError) as caught:
            adapter.generate(REQUEST)
        assert caught.value.kind == kind

    @pytest.mark.parametrize(
        ("error", "kind"),
        [
            (lambda: status_error(anthropic.AuthenticationError, 401), "auth"),
            (lambda: status_error(anthropic.RateLimitError, 429), "rate-limited"),
            (lambda: status_error(anthropic.BadRequestError, 400), "bad-request"),
            (lambda: status_error(anthropic.InternalServerError, 500), "unavailable"),
            (lambda: anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com")), "timeout"),
            (
                lambda: anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com")),
                "unavailable",
            ),
        ],
    )
    def test_maps_sdk_errors_to_safe_messages(self, error, kind: str) -> None:
        adapter, _ = provider(error())
        with pytest.raises(ModelError) as caught:
            adapter.generate(REQUEST)
        assert caught.value.kind == kind
        assert "secret" not in caught.value.message

    def test_unconfigured_provider_never_fabricates(self) -> None:
        adapter = AnthropicProvider(api_key=None, model="claude-opus-5-5", max_retries=2, refusal_fallback=True)
        assert not adapter.configured
        with pytest.raises(ModelError) as caught:
            adapter.generate(REQUEST)
        assert caught.value.kind == "not-configured" and "ANTHROPIC_API_KEY" in caught.value.message


class TestSettings:
    def base(self, **overrides) -> Settings:
        return Settings(_env_file=None, database_url="postgresql://u@db/omniora", **overrides)

    def test_development_defaults(self) -> None:
        settings = self.base()
        assert settings.cookie_secure is False
        assert settings.database_url.startswith("postgresql+psycopg://")
        assert settings.model_configured is False

    def test_production_requires_secure_explicit_configuration(self) -> None:
        with pytest.raises(ValidationError, match="COOKIE_SECURE"):
            self.base(env="production", cookie_secure=False, cors_origins=["https://app.example.com"])
        with pytest.raises(ValidationError, match="explicit origins"):
            self.base(env="production", cors_origins="*")
        with pytest.raises(ValidationError, match="https"):
            self.base(env="production", cors_origins="http://app.example.com")
        assert self.base(env="production", cors_origins="https://app.example.com").cookie_secure is True

    def test_rejects_non_postgres_urls(self) -> None:
        with pytest.raises(ValidationError, match="PostgreSQL"):
            Settings(_env_file=None, database_url="sqlite:///omniora.db")

    def test_api_key_is_secret(self, monkeypatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123")
        settings = self.base()
        assert settings.model_configured
        assert "sk-ant-test-123" not in repr(settings) and "sk-ant-test-123" not in str(settings.model_dump())


class TestRedaction:
    def test_redacts_sensitive_keys_and_key_shaped_values(self) -> None:
        redacted = redact({"password": "hunter2", "nested": {"api_key": "x", "note": "key sk-ant-abc123 leaked"}})
        assert redacted == {
            "password": "[redacted]",
            "nested": {"api_key": "[redacted]", "note": "key [redacted] leaked"},
        }

    def test_json_formatter_redacts_extras(self) -> None:
        record = logging.makeLogRecord({"msg": "token sk-ant-zzz", "levelname": "INFO", "session_token": "abc"})
        payload = json.loads(JsonFormatter().format(record))
        assert payload["message"] == "token [redacted]" and payload["session_token"] == "[redacted]"


def test_sliding_window_limiter() -> None:
    now = [0.0]
    limiter = SlidingWindowLimiter(2, 10, clock=lambda: now[0])
    assert limiter.hit("k") is None and limiter.hit("k") is None
    assert limiter.hit("k") == pytest.approx(10)
    now[0] = 10.5
    assert limiter.hit("k") is None
