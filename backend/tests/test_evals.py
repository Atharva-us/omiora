"""Planning evaluation fixtures, graded deterministically (no model calls)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from omniora_api.evals.discovery import grade_discovery, load_discovery_fixtures
from omniora_api.evals.graders import grade, load_fixtures

FIXTURES = load_fixtures()


def test_fixture_set_covers_the_required_scenarios() -> None:
    names = {fixture.name for fixture in FIXTURES}
    assert names == {
        "ecommerce-website",
        "flutter-mobile-app",
        "fullstack-saas",
        "incomplete-requirements",
        "conflicting-technology-preferences",
        "invalid-model-output",
        "cyclic-task-dependencies",
    }
    # Candidates are labelled honestly: none claims to be recorded model output.
    assert all("model output" not in f.candidate_source or "not model output" in f.candidate_source for f in FIXTURES)


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.name for f in FIXTURES])
def test_reference_candidates_meet_expectations(fixture) -> None:
    result = grade(fixture)
    assert result.passed, f"{result.checks} {result.problems}"


def test_graders_fail_plans_that_miss_coverage_or_questions() -> None:
    ecommerce = next(f for f in FIXTURES if f.name == "ecommerce-website")
    # A plan that silently drops the note's requirement and asks nothing.
    plan = json.loads(ecommerce.candidate_output.replace("discount", "loyalty"))
    plan["open_questions"] = []
    result = grade(ecommerce, json.dumps(plan))
    assert not result.passed
    assert result.checks["covers:discount codes (from notes)"] is False
    assert result.checks["asks:payment provider"] is False

    vague = next(f for f in FIXTURES if f.name == "incomplete-requirements")
    plan = json.loads(vague.candidate_output)
    for question in plan["open_questions"]:
        question["blocking"] = False
    assert grade(vague, json.dumps(plan)).checks["blocking_questions>=2"] is False


def test_tenant_isolation_gap_in_a_recorded_live_plan_is_caught() -> None:
    # Real Groq output from the 2026-10-29 live round: valid and acyclic, but with no requirement or task
    # keeping one workspace's data from another. The grader must keep failing it on that topic alone.
    path = Path(__file__).parent / "data" / "recorded_saas_plan_without_isolation.json"
    recorded = json.loads(path.read_text("utf-8"))
    saas = next(f for f in FIXTURES if f.name == "fullstack-saas")
    result = grade(saas, json.dumps(recorded["plan"]))
    failed = [name for name, ok in result.checks.items() if not ok]
    assert failed == ["covers:tenant isolation"]


DISCOVERY_FIXTURES = load_discovery_fixtures()


def test_discovery_fixture_set_covers_the_required_scenarios() -> None:
    assert {f.name for f in DISCOVERY_FIXTURES} == {
        "vague-brief",
        "multi-tenant-saas",
        "contradictory-answers",
        "clear-project",
        "unknown-critical-answer",
        "invented-answer",
    }
    assert all("not model output" in f.candidate_source for f in DISCOVERY_FIXTURES)


@pytest.mark.parametrize("fixture", DISCOVERY_FIXTURES, ids=[f.name for f in DISCOVERY_FIXTURES])
def test_discovery_reference_outputs_meet_expectations(fixture) -> None:
    result = grade_discovery(fixture)
    assert result.passed, f"{result.checks} {result.problems}"


def test_discovery_graders_fail_outputs_that_miss_expectations() -> None:
    by_name = {f.name: f for f in DISCOVERY_FIXTURES}

    saas = by_name["multi-tenant-saas"]
    vague_criteria = json.loads(saas.candidate_output)
    vague_criteria["operations"][3]["acceptance_criteria"] = ["Workspaces are separated."]
    assert grade_discovery(saas, json.dumps(vague_criteria)).checks["isolation_criteria_prove_denial"] is False

    vague = by_name["vague-brief"]
    invented = json.loads(vague.candidate_output)
    invented["operations"] += [dict(invented["operations"][0], statement=f"Invented feature {n}.") for n in range(3)]
    invented["questions"] = []
    graded = grade_discovery(vague, json.dumps(invented))
    # Dropping the questions about users and features is now rejected by the validator itself.
    assert graded.checks == {"valid": False}
    assert any("topic 'users'" in p for p in graded.problems)
    invented["questions"] = json.loads(vague.candidate_output)["questions"]
    still_invents = grade_discovery(vague, json.dumps(invented))
    assert still_invents.checks["active_requirements<=3"] is False

    unknown = by_name["unknown-critical-answer"]
    as_fact = json.loads(unknown.candidate_output)
    as_fact["operations"][0].update(source="answer", evidence=["answer:DQ-001"])
    assert grade_discovery(unknown, json.dumps(as_fact)).checks == {"valid": False}

    contradictory = by_name["contradictory-answers"]
    picked_a_side = json.loads(contradictory.candidate_output)
    picked_a_side["questions"] = []
    picked_a_side["readiness"] = {"ready": False, "blockers": []}
    unexplained = grade_discovery(contradictory, json.dumps(picked_a_side))  # "not ready" with nothing blocking
    assert unexplained.checks == {"valid": False} and any("Nothing blocks readiness" in p for p in unexplained.problems)
    picked_a_side["readiness"] = {"ready": True, "blockers": []}
    graded = grade_discovery(contradictory, json.dumps(picked_a_side))
    assert graded.checks["blocking_questions>=1"] is False and graded.checks["ready=False"] is False
