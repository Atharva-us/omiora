"""Test doubles and builders. Nothing here is importable by application code."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from omniora_api.llm.base import ModelError, ModelRequest, ModelResponse, ModelUsage


class FakeClock:
    def __init__(self, start: datetime | None = None) -> None:
        self.current = start or datetime(2026, 10, 29, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


Scripted = str | ModelError | Callable[[ModelRequest], str]


class ScriptedProvider:
    """Returns pre-scripted outputs in order. Used only in tests: production never fabricates output."""

    name = "scripted"
    model = "scripted-model"

    def __init__(self, *outputs: Scripted) -> None:
        self._outputs = list(outputs)
        self.requests: list[ModelRequest] = []

    @property
    def configured(self) -> bool:
        return True

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if not self._outputs:
            raise AssertionError("ScriptedProvider ran out of outputs")
        output = self._outputs.pop(0)
        if isinstance(output, ModelError):
            raise output
        text = output(request) if callable(output) else output
        return ModelResponse(
            text=text,
            provider=self.name,
            model=self.model,
            stop_reason="end_turn",
            usage=ModelUsage(input_tokens=100, output_tokens=200),
            request_id="req_test",
            latency_ms=5,
        )


def model_error(kind: str, message: str = "provider failure") -> ModelError:
    return ModelError(kind, message, provider="scripted", model="scripted-model")  # type: ignore[arg-type]


def configuration(**overrides: Any) -> dict[str, Any]:
    base = {
        "name": "Maker Market",
        "description": "A storefront for handmade goods",
        "platform": "website",
        "referenceUrl": "",
        "stack": {"mode": "recommend"},
        "requirements": {"features": [], "custom": ""},
    }
    base.update(overrides)
    return base


def plan(**overrides: Any) -> dict[str, Any]:
    """A plan that passes validation for a `recommend`-mode website configuration."""
    base: dict[str, Any] = {
        "summary": "An online storefront where makers list and sell handmade goods.",
        "requirements": [
            {
                "id": "R1",
                "statement": "Shoppers can browse products.",
                "kind": "functional",
                "priority": "must",
                "source": "user",
            },
            {
                "id": "R2",
                "statement": "Shoppers can pay securely.",
                "kind": "functional",
                "priority": "must",
                "source": "inferred",
            },
        ],
        "assumptions": ["Payments use a hosted provider."],
        "open_questions": [
            {
                "id": "Q1",
                "question": "Which payment provider?",
                "why_it_matters": "Affects checkout integration.",
                "blocking": False,
            }
        ],
        "recommended_stack": {
            "technologies": ["nextjs", "postgresql"],
            "rationale": "SEO-friendly storefront with relational data.",
        },
        "tasks": [
            {
                "key": "T1",
                "title": "Design the data model",
                "description": "Products, orders, users.",
                "acceptance_criteria": ["Schema reviewed"],
                "depends_on": [],
                "requirement_ids": ["R1", "R2"],
                "suggested_agent": "database-engineer",
            },
            {
                "key": "T2",
                "title": "Build the catalogue",
                "description": "Product listing and detail pages.",
                "acceptance_criteria": ["Products render"],
                "depends_on": ["T1"],
                "requirement_ids": ["R1"],
                "suggested_agent": "frontend-engineer",
            },
            {
                "key": "T3",
                "title": "Checkout",
                "description": "Cart and hosted payment.",
                "acceptance_criteria": ["Test payment succeeds"],
                "depends_on": ["T1", "T2"],
                "requirement_ids": ["R2"],
                "suggested_agent": "backend-engineer",
            },
        ],
        "required_approvals": [{"gate": "plan", "description": "Approve scope before any work starts."}],
    }
    result = copy.deepcopy(base)
    result.update(overrides)
    return result


def plan_json(**overrides: Any) -> str:
    return json.dumps(plan(**overrides))


# --- Requirements Analyst -----------------------------------------------------------------


def requirement_op(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "op": "add",
        "id": "",
        "statement": "Shoppers can browse products by category.",
        "kind": "functional",
        "priority": "must",
        "confidence": "high",
        "source": "brief",
        "evidence": ["brief:description"],
        "acceptance_criteria": ["A shopper can open a category and see its products."],
        "tags": [],
        "reason": "",
    }
    base.update(overrides)
    return base


def analyst_context(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "goal": "Let makers sell handmade goods online.",
        "scope": "Storefront, checkout, and order management for one shop.",
        "platform": "website",
        "deployment": "",
        "personas": [{"name": "Shopper", "description": "Buys handmade goods."}],
        "tenancy": "single",
        "constraints": [],
        "integrations": [],
        "out_of_scope": [],
    }
    base.update(overrides)
    return base


def question(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "prompt": "Which payment methods must checkout accept?",
        "why": "Determines the payment integration.",
        "kind": "multiple-choice",
        "options": ["Cards", "PayPal", "Bank transfer"],
        "blocking": True,
        "topic": "scope",
        "relates_to": [],
    }
    base.update(overrides)
    return base


def analyst_output(**overrides: Any) -> dict[str, Any]:
    """A valid first-turn output for the default `configuration()` (single-tenant storefront)."""
    base: dict[str, Any] = {
        "context": analyst_context(),
        "operations": [requirement_op()],
        "questions": [question()],
        "withdraw_questions": [],
        "assumptions": [],
        "readiness": {"ready": False, "blockers": ["Payment methods are unknown."]},
        "decisions": ["Started from the brief's description."],
    }
    result = copy.deepcopy(base)
    result.update(overrides)
    return result


def analyst_json(**overrides: Any) -> str:
    return json.dumps(analyst_output(**overrides))
