"""The Requirements Analyst agent loop in isolation: retries, backoff, and request budgeting."""

from __future__ import annotations

import json

from omniora_api.agents.requirements_analyst import (
    SYSTEM_PROMPT,
    DiscoveryInput,
    build_user_content,
    estimate_tokens,
    run_requirements_analyst,
)
from omniora_api.domain.projects import ProjectConfiguration
from omniora_api.domain.requirements import QuestionState, analyst_output_schema
from omniora_api.llm.base import ModelError

from .support import ScriptedProvider, analyst_json, configuration


def discovery(**overrides) -> DiscoveryInput:
    values = {
        "configuration": ProjectConfiguration.model_validate(configuration()),
        "notes": [],
        "previous": None,
        "questions": (),
        "answers": {},
        "turn": 1,
        "max_turns": 8,
        "final_turn": False,
        "first_question_number": 1,
    }
    values.update(overrides)
    return DiscoveryInput(**values)


def run(provider, discovery_input, **overrides):
    options = {
        "max_attempts": 3,
        "max_output_tokens": 3000,
        "request_token_budget": 7600,
        "effort": "medium",
        "timeout_seconds": 30,
    }
    options.update(overrides)
    return run_requirements_analyst(provider, discovery_input, **options)


def test_rate_limit_waits_for_retry_after_then_succeeds() -> None:
    limited = ModelError("rate-limited", "Slow down.", provider="scripted", model="m", retry_after_seconds=7)
    waits: list[float] = []
    result = run(ScriptedProvider(limited, analyst_json()), discovery(), sleep=waits.append)
    assert waits == [7] and result.turn is not None and result.turn.document is not None
    assert [a.outcome for a in result.attempts] == ["provider-error", "succeeded"]


def test_a_limit_that_outlasts_the_wait_cap_stops_the_turn_immediately() -> None:
    daily = ModelError("rate-limited", "Quota.", provider="scripted", model="m", retry_after_seconds=3600)
    waits: list[float] = []
    provider = ScriptedProvider(daily, analyst_json())
    result = run(provider, discovery(), sleep=waits.append)
    assert result.turn is None and result.failure_code == "provider-rate-limited"
    assert len(provider.requests) == 1 and waits == []


def test_a_provider_rejected_output_is_validated_and_explained_on_the_next_attempt() -> None:
    rejected = ModelError(
        "invalid-output",
        "The model's output did not match the required schema.",
        provider="scripted",
        model="m",
        raw_output='{"context": {}}',
    )
    provider = ScriptedProvider(rejected, analyst_json())
    result = run(provider, discovery(), sleep=lambda _: None)
    assert result.turn is not None
    assert result.attempts[0].raw_output == '{"context": {}}' and result.attempts[0].validation_errors
    assert "<validation_errors>" in provider.requests[1].user_content


def test_feedback_is_sent_back_and_attempts_are_bounded() -> None:
    provider = ScriptedProvider("not json", "{}", "{}")
    result = run(provider, discovery())
    assert result.turn is None and result.failure_code == "invalid-output" and len(provider.requests) == 3
    assert "<validation_errors>" in provider.requests[1].user_content


def test_never_marks_a_failed_provider_call_as_a_turn() -> None:
    down = ModelError("unavailable", "Overloaded.", provider="scripted", model="m")
    result = run(ScriptedProvider(down, down, down), discovery(), sleep=lambda _: None)
    assert result.turn is None and result.failure_code == "provider-unavailable"


def test_output_budget_shrinks_to_fit_before_refusing() -> None:
    provider = ScriptedProvider(analyst_json())
    result = run(provider, discovery(), request_token_budget=6000, max_output_tokens=5000)
    sent = provider.requests[0].max_output_tokens
    assert result.turn is not None and 3000 <= sent < 5000  # shrunk to fit, above the floor
    refused = ScriptedProvider()
    tiny = run(refused, discovery(), request_token_budget=4000, max_output_tokens=5000)
    assert tiny.failure_code == "context-too-large" and refused.requests == []


def test_prompt_lists_question_topics_separately_from_tags() -> None:
    from omniora_api.agents.requirements_analyst import SYSTEM_PROMPT as prompt

    assert "a topic (only these: scope, users, tenancy" in " ".join(prompt.split())
    assert "they differ from the tags" in prompt


def test_compact_summary_is_used_when_the_full_one_would_not_fit() -> None:
    answered = tuple(
        QuestionState(
            key=f"DQ-{n:03d}",
            prompt=f"Question number {n} about scope details?",
            kind="single-choice",
            options=("Option A with a long label", "Option B with a long label", "Option C with a long label"),
            blocking=False,
            topic="scope",
            status="answered",
        )
        for n in range(1, 41)
    )
    big = discovery(questions=answered, answers={q.key: "Option A with a long label" for q in answered})
    full = build_user_content(big)
    compact = build_user_content(big, compact=True)
    assert len(compact) < len(full) and '"options"' not in compact
    fixed = estimate_tokens(json.dumps(analyst_output_schema())) + 1500  # schema + output budget
    full_size = estimate_tokens(SYSTEM_PROMPT + full) + fixed
    compact_size = estimate_tokens(SYSTEM_PROMPT + compact) + fixed
    provider = ScriptedProvider(analyst_json())
    run(provider, big, request_token_budget=(full_size + compact_size) // 2, max_output_tokens=1500)
    assert provider.requests and '"options"' not in provider.requests[0].user_content
