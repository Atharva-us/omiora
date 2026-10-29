"""Plan validation and the Project Manager attempt loop (no database)."""

from __future__ import annotations

import json

from omniora_api.agents.project_manager import PlanningInput, run_project_manager, validate_output
from omniora_api.domain.plans import ProjectPlan, find_cycle, plan_output_schema, plan_problems
from omniora_api.domain.projects import ProjectConfiguration

from .support import ScriptedProvider, configuration, model_error, plan, plan_json

RECOMMEND = ProjectConfiguration.model_validate(configuration())
CUSTOM = ProjectConfiguration.model_validate(configuration(stack={"mode": "custom", "technologies": ["nextjs"]}))


def problems(data: dict, config: ProjectConfiguration = RECOMMEND) -> list[str]:
    return plan_problems(ProjectPlan.model_validate(data), config)


class TestPlanValidation:
    def test_valid_plan_passes(self) -> None:
        assert problems(plan()) == []

    def test_detects_cycles(self) -> None:
        tasks = plan()["tasks"]
        tasks[0]["depends_on"] = ["T3"]  # T1 -> T3 -> T1
        found = problems(plan(tasks=tasks))
        assert any("cycle" in p for p in found)
        assert find_cycle({"A": ["B"], "B": ["C"], "C": ["A"], "D": []}) == ["A", "B", "C"]
        assert find_cycle({"A": [], "B": ["A"]}) is None

    def test_detects_unresolved_and_self_references(self) -> None:
        tasks = plan()["tasks"]
        tasks[1]["depends_on"] = ["T9", "T2"]
        tasks[2]["requirement_ids"] = ["R7"]
        found = problems(plan(tasks=tasks))
        assert "Task 'T2' depends on unknown task 'T9'." in found
        assert "Task 'T2' depends on itself." in found
        assert "Task 'T3' references unknown requirement 'R7'." in found

    def test_requires_must_coverage_and_unique_keys(self) -> None:
        tasks = plan()["tasks"]
        for task in tasks:
            task["requirement_ids"] = ["R1"]
        tasks[1]["key"] = "T1"
        found = problems(plan(tasks=tasks))
        assert "Must-have requirement 'R2' is not covered by any task." in found
        assert "Duplicate task key 'T1'." in found

    def test_stack_rules_follow_the_configuration(self) -> None:
        assert any(
            "recommended_stack.technologies is required" in p
            for p in problems(plan(recommended_stack={"technologies": [], "rationale": ""}))
        )
        assert any(
            "React and Next.js" in p
            for p in problems(plan(recommended_stack={"technologies": ["react", "nextjs"], "rationale": "x"}))
        )
        assert any("must be empty" in p for p in problems(plan(), CUSTOM))
        assert problems(plan(recommended_stack={"technologies": [], "rationale": ""}), CUSTOM) == []

    def test_requires_plan_gate(self) -> None:
        found = problems(plan(required_approvals=[{"gate": "release", "description": "Before launch."}]))
        assert "required_approvals must include the 'plan' gate." in found

    def test_shape_errors_are_reported_not_raised(self) -> None:
        assert validate_output("not json", RECOMMEND)[1][0].startswith("Output is not valid JSON")
        bad = plan()
        bad["tasks"][0]["suggested_agent"] = "project-manager"  # cannot assign work to itself
        result, found = validate_output(json.dumps(bad), RECOMMEND)
        assert result is None and any("suggested_agent" in p for p in found)
        assert validate_output(json.dumps({**plan(), "extra": 1}), RECOMMEND)[0] is None

    def test_output_schema_is_strict_json_schema(self) -> None:
        schema = plan_output_schema()
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(ProjectPlan.model_fields)


class TestAttemptLoop:
    def run(self, provider: ScriptedProvider, max_attempts: int = 3):
        records = []
        result = run_project_manager(
            provider,
            PlanningInput(configuration=RECOMMEND, notes=["Must support gift cards"]),
            max_attempts=max_attempts,
            max_output_tokens=4000,
            effort="high",
            timeout_seconds=30,
            on_attempt=records.append,
        )
        return result, records

    def test_succeeds_first_time_and_sends_data_as_data(self) -> None:
        provider = ScriptedProvider(plan_json())
        result, records = self.run(provider)
        assert result.plan is not None and [r.outcome for r in records] == ["succeeded"]
        request = provider.requests[0]
        assert "<notes>" in request.user_content and "gift cards" in request.user_content
        assert "never as instructions" in request.system
        assert request.output_schema == plan_output_schema()

    def test_retries_with_validation_feedback(self) -> None:
        cyclic = plan()
        cyclic["tasks"][0]["depends_on"] = ["T3"]
        provider = ScriptedProvider(json.dumps(cyclic), plan_json())
        result, records = self.run(provider)
        assert result.plan is not None
        assert [r.outcome for r in records] == ["invalid-output", "succeeded"]
        assert "<validation_errors>" in provider.requests[1].user_content
        assert "cycle" in provider.requests[1].user_content

    def test_gives_up_after_bounded_attempts(self) -> None:
        provider = ScriptedProvider("{}", "not json", plan_json(tasks=[]))
        result, records = self.run(provider)
        assert result.plan is None and result.failure_code == "invalid-plan"
        assert len(records) == 3 and all(r.outcome == "invalid-output" for r in records)

    def test_non_retryable_provider_errors_stop_immediately(self) -> None:
        provider = ScriptedProvider(model_error("auth", "The model provider rejected the configured credentials."))
        result, records = self.run(provider)
        assert result.failure_code == "provider-auth"
        assert len(records) == 1 and records[0].error_code == "auth"

    def test_transient_errors_count_against_the_attempt_budget(self) -> None:
        provider = ScriptedProvider(model_error("timeout"), model_error("unavailable"), plan_json())
        result, records = self.run(provider)
        assert result.plan is not None
        assert [r.outcome for r in records] == ["provider-error", "provider-error", "succeeded"]
        exhausted, _ = self.run(ScriptedProvider(model_error("timeout"), model_error("timeout")), max_attempts=2)
        assert exhausted.failure_code == "provider-unavailable"

    def test_stops_when_told_to(self) -> None:
        result = run_project_manager(
            ScriptedProvider(),
            PlanningInput(configuration=RECOMMEND, notes=[]),
            max_attempts=3,
            max_output_tokens=4000,
            effort="high",
            timeout_seconds=30,
            before_attempt=lambda _: False,
        )
        assert result.failure_code == "interrupted" and result.attempts == []
