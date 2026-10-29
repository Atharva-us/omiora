"""Groq adapter, provider selection, and failure handling. Mocked HTTP only: no live key is needed.

The real `groq` SDK runs against an `httpx.MockTransport`, so request serialisation, SDK retries,
and SDK exception classes are exercised rather than bypassed.
"""

from __future__ import annotations

import json
import logging

import groq
import httpx
import pytest

from omniora_api.agents.project_manager import PlanningInput, backoff_seconds, run_project_manager
from omniora_api.config import Settings
from omniora_api.domain.projects import ProjectConfiguration
from omniora_api.llm.anthropic_provider import AnthropicProvider
from omniora_api.llm.base import ModelError, ModelRequest
from omniora_api.llm.factory import build_planning_provider
from omniora_api.llm.groq_provider import GroqProvider
from omniora_api.logging_setup import JsonFormatter

from .support import ScriptedProvider, configuration, model_error, plan_json

FAKE_KEY = "gsk_" + "T3st" * 12  # shaped like a Groq key; not a real credential
REQUEST = ModelRequest(
    system="sys",
    user_content="brief",
    output_schema={"type": "object"},
    max_output_tokens=6000,
    effort="medium",
    timeout_seconds=30,
)
CONFIG = ProjectConfiguration.model_validate(configuration())


def completion(content: str | None, finish_reason: str = "stop", model: str = "openai/gpt-oss-120b") -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1761739200,
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 1200, "completion_tokens": 900, "total_tokens": 2100},
    }


class FakeGroqApi:
    """Serves queued HTTP responses and records every request the SDK sends."""

    def __init__(self, *responses: httpx.Response | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(response, Exception):
            raise response
        return response

    def provider(self, model: str = "openai/gpt-oss-120b", max_retries: int = 2) -> GroqProvider:
        client = groq.Groq(
            api_key=FAKE_KEY,
            max_retries=max_retries,
            http_client=httpx.Client(transport=httpx.MockTransport(self.handler)),
        )
        return GroqProvider(api_key=None, model=model, max_retries=max_retries, client=client)

    def body(self, index: int = 0) -> dict:
        return json.loads(self.requests[index].content)


def ok(content: str | None, **kwargs) -> httpx.Response:
    return httpx.Response(200, json=completion(content, **kwargs), headers={"x-request-id": "req_groq_1"})


def error(
    status: int, code: str = "", headers: dict | None = None, message: str = "", failed_generation: str = ""
) -> httpx.Response:
    body = {
        "error": {
            "message": message or f"provider says {FAKE_KEY} is involved",
            "type": "invalid_request_error",
            "code": code,
            **({"failed_generation": failed_generation} if failed_generation else {}),
        }
    }
    return httpx.Response(status, json=body, headers=headers or {})


FAST_RETRY = {"retry-after-ms": "1"}  # keeps SDK transport retries instant in tests


class TestRequestAndParsing:
    def test_strict_structured_output_request_and_parsed_response(self) -> None:
        api = FakeGroqApi(ok(plan_json()))
        response = api.provider().generate(REQUEST)
        sent = api.body()
        assert sent["model"] == "openai/gpt-oss-120b"
        assert sent["response_format"] == {
            "type": "json_schema",
            "json_schema": {"name": "project_plan", "schema": {"type": "object"}, "strict": True},
        }
        assert sent["max_completion_tokens"] == 6000
        assert sent["reasoning_effort"] == "medium" and sent["include_reasoning"] is False
        assert [m["role"] for m in sent["messages"]] == ["system", "user"]
        assert api.requests[0].headers["authorization"] == f"Bearer {FAKE_KEY}"  # sent only to the provider
        assert json.loads(response.text)["summary"]
        assert response.usage.input_tokens == 1200 and response.usage.output_tokens == 900
        assert response.provider == "groq" and response.request_id

    def test_effort_beyond_high_maps_to_high(self) -> None:
        api = FakeGroqApi(ok(plan_json()))
        api.provider().generate(
            ModelRequest(system="s", user_content="u", output_schema={}, max_output_tokens=2000, effort="max")
        )
        assert api.body()["reasoning_effort"] == "high"

    def test_models_without_schema_support_use_json_mode_with_the_schema_in_the_prompt(self) -> None:
        api = FakeGroqApi(ok(plan_json(), model="llama-3.1-8b-instant"))
        api.provider(model="llama-3.1-8b-instant").generate(REQUEST)
        sent = api.body()
        assert sent["response_format"] == {"type": "json_object"}
        assert "reasoning_effort" not in sent and "include_reasoning" not in sent
        assert "<output_json_schema>" in sent["messages"][1]["content"]

    def test_truncated_output_is_reported_not_parsed(self) -> None:
        api = FakeGroqApi(ok('{"summary": "cut', finish_reason="length"))
        with pytest.raises(ModelError) as caught:
            api.provider().generate(REQUEST)
        assert caught.value.kind == "truncated"


class TestFailures:
    def failure(self, api: FakeGroqApi, max_retries: int = 2) -> ModelError:
        with pytest.raises(ModelError) as caught:
            api.provider(max_retries=max_retries).generate(REQUEST)
        return caught.value

    def test_authentication_failure_is_permanent_and_not_retried(self) -> None:
        api = FakeGroqApi(error(401, "invalid_api_key"))
        err = self.failure(api)
        assert err.kind == "auth" and not err.retryable
        assert len(api.requests) == 1  # no transport retries either

    def test_rate_limits_are_retried_by_the_sdk_then_surface_retry_after(self) -> None:
        api = FakeGroqApi(error(429, "rate_limit_exceeded", {**FAST_RETRY, "retry-after": "7"}))
        err = self.failure(api, max_retries=2)
        assert err.kind == "rate-limited" and err.retryable
        assert err.retry_after_seconds == 7.0
        assert len(api.requests) == 3  # 1 + 2 bounded SDK retries

    def test_request_larger_than_the_token_budget_is_permanent(self) -> None:
        err = self.failure(FakeGroqApi(error(413, "request_too_large")))
        assert err.kind == "bad-request" and not err.retryable
        assert "OMNIORA_PM_MAX_OUTPUT_TOKENS" in err.message

    def test_schema_rejection_by_the_provider_is_a_retryable_invalid_output(self) -> None:
        err = self.failure(FakeGroqApi(error(400, "json_validate_failed")))
        assert err.kind == "invalid-output" and err.retryable

    def test_rejected_generation_is_kept_for_diagnosis_but_the_message_is_not(self) -> None:
        err = self.failure(FakeGroqApi(error(400, "json_validate_failed", failed_generation='{"tags": ["payment"]}')))
        assert err.kind == "invalid-output" and err.raw_output == '{"tags": ["payment"]}'
        assert FAKE_KEY not in err.message

    def test_running_out_of_output_tokens_is_reported_as_truncation(self) -> None:
        # Seen live: Groq reports a reasoning-heavy output cut off by max_completion_tokens as a schema failure.
        message = "max completion tokens reached before generating a valid document: the output was truncated"
        err = self.failure(FakeGroqApi(error(400, "json_validate_failed", message=message)))
        assert err.kind == "truncated" and err.retryable
        assert "output tokens" in err.message and "truncated to fit" not in err.message

    def test_other_bad_requests_are_permanent(self) -> None:
        err = self.failure(FakeGroqApi(error(400, "model_decommissioned")))
        assert err.kind == "bad-request" and not err.retryable

    def test_timeouts_are_retried_a_bounded_number_of_times(self) -> None:
        api = FakeGroqApi(httpx.ReadTimeout("slow"))
        err = self.failure(api, max_retries=1)
        assert err.kind == "timeout" and len(api.requests) == 2

    def test_server_errors_are_unavailable(self) -> None:
        api = FakeGroqApi(error(503, headers=FAST_RETRY))
        err = self.failure(api, max_retries=1)
        assert err.kind == "unavailable" and len(api.requests) == 2

    def test_error_messages_never_contain_the_key_or_provider_body(self) -> None:
        for response in (error(401), error(400), error(429, headers=FAST_RETRY), error(500, headers=FAST_RETRY)):
            err = self.failure(FakeGroqApi(response), max_retries=0)
            assert FAKE_KEY not in err.message and "provider says" not in err.message

    def test_missing_key_never_calls_the_api(self) -> None:
        provider = GroqProvider(api_key=None, model="openai/gpt-oss-120b", max_retries=2)
        assert not provider.configured
        with pytest.raises(ModelError) as caught:
            provider.generate(REQUEST)
        assert caught.value.kind == "not-configured" and "GROQ_API_KEY" in caught.value.message


class TestAgentWithGroq:
    def run(self, provider, sleeps: list[float] | None = None, max_attempts: int = 3):
        return run_project_manager(
            provider,
            PlanningInput(configuration=CONFIG, notes=[]),
            max_attempts=max_attempts,
            max_output_tokens=6000,
            effort="medium",
            timeout_seconds=30,
            sleep=(sleeps.append if sleeps is not None else lambda _: None),
        )

    def test_malformed_output_is_rejected_and_retried_through_the_real_adapter(self) -> None:
        api = FakeGroqApi(ok('{"summary": "missing everything else"}'), ok(plan_json()))
        result = self.run(api.provider())
        assert result.plan is not None
        assert [a.outcome for a in result.attempts] == ["invalid-output", "succeeded"]
        assert "<validation_errors>" in api.body(1)["messages"][1]["content"]

    def test_provider_failure_never_produces_a_plan(self) -> None:
        result = self.run(FakeGroqApi(error(401)).provider())
        assert result.plan is None and result.failure_code == "provider-auth"
        assert len(result.attempts) == 1 and result.attempts[0].outcome == "provider-error"

    def test_rate_limits_wait_for_retry_after_and_stay_bounded(self) -> None:
        limited = ModelError("rate-limited", "limited", provider="groq", model="m", retry_after_seconds=7)
        sleeps: list[float] = []
        result = self.run(ScriptedProvider(limited, plan_json()), sleeps)
        assert result.plan is not None and sleeps == [7]

        sleeps.clear()
        always = ModelError("rate-limited", "limited", provider="groq", model="m", retry_after_seconds=500)
        exhausted = self.run(ScriptedProvider(always, always, always), sleeps)
        assert exhausted.plan is None and exhausted.failure_code == "provider-unavailable"
        assert sleeps == [60, 60]  # capped, and no pointless wait after the final attempt

    def test_backoff_policy(self) -> None:
        assert backoff_seconds(model_error("rate-limited"), 1) == 2
        assert backoff_seconds(model_error("rate-limited"), 9) == 60
        assert backoff_seconds(model_error("timeout"), 1) == 0


class TestProviderSelection:
    def settings(self, **overrides) -> Settings:
        return Settings(_env_file=None, database_url="postgresql://u@db/omniora", **overrides)

    def test_anthropic_stays_the_default_even_when_a_groq_key_exists(self, monkeypatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", FAKE_KEY)
        settings = self.settings()
        provider = build_planning_provider(settings)
        assert isinstance(provider, AnthropicProvider) and provider.model == "claude-opus-5-5"
        assert settings.model_configured is False  # the Groq key does not configure Anthropic
        assert (settings.planning_effort, settings.planning_max_output_tokens) == ("high", 16000)

    def test_groq_selected_explicitly_uses_its_key_and_defaults(self, monkeypatch) -> None:
        monkeypatch.setenv("groq_api_key", FAKE_KEY)  # lower-case names work, as in a hand-written .env
        monkeypatch.setenv("OMNIORA_MODEL_PROVIDER", "groq")
        settings = self.settings()
        provider = build_planning_provider(settings)
        assert isinstance(provider, GroqProvider) and provider.configured
        assert provider.model == "openai/gpt-oss-120b"
        assert (settings.planning_effort, settings.planning_max_output_tokens) == ("medium", 6000)
        assert FAKE_KEY not in repr(settings) and FAKE_KEY not in str(settings.model_dump())

    def test_overrides_and_missing_key(self, monkeypatch) -> None:
        monkeypatch.setenv("OMNIORA_MODEL_PROVIDER", "groq")
        monkeypatch.setenv("OMNIORA_PM_MODEL", "openai/gpt-oss-20b")
        monkeypatch.setenv("OMNIORA_PM_MAX_OUTPUT_TOKENS", "4000")
        settings = self.settings()
        assert settings.planning_model == "openai/gpt-oss-20b" and settings.planning_max_output_tokens == 4000
        assert settings.model_configured is False
        assert build_planning_provider(settings).configured is False

    def test_blank_key_is_not_configured(self, monkeypatch) -> None:
        monkeypatch.setenv("OMNIORA_MODEL_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "   ")
        assert self.settings().model_configured is False

    def test_unknown_provider_is_rejected(self, monkeypatch) -> None:
        monkeypatch.setenv("OMNIORA_MODEL_PROVIDER", "openai")
        with pytest.raises(ValueError, match="model_provider"):
            self.settings()


def test_groq_keys_are_redacted_from_logs() -> None:
    record = logging.makeLogRecord({"msg": f"calling with {FAKE_KEY}", "levelname": "ERROR", "detail": f"k={FAKE_KEY}"})
    output = JsonFormatter().format(record)
    assert FAKE_KEY not in output and output.count("[redacted]") == 2


@pytest.mark.usefixtures("factory")
def test_worker_records_a_failed_run_and_no_plan_when_groq_rejects_credentials(signed_in, make_worker) -> None:
    client = signed_in()
    project_id = client.post("/api/v1/projects", json=configuration()).json()["id"]
    run_id = client.post(
        f"/api/v1/projects/{project_id}/runs",
        headers={"Idempotency-Key": "key-groq-001"},
        json={"withoutRequirements": True},
    ).json()["id"]
    make_worker(FakeGroqApi(error(401)).provider()).run_once()
    body = client.get(f"/api/v1/runs/{run_id}").json()
    assert body["run"]["state"] == "failed" and body["run"]["failureCode"] == "provider-auth"
    assert body["plan"] is None and body["tasks"] == []
    assert body["attempts"][0]["errorCode"] == "auth" and FAKE_KEY not in json.dumps(body)
