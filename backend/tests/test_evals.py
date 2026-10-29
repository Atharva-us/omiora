"""Planning evaluation fixtures, graded deterministically (no model calls)."""

from __future__ import annotations

import json

import pytest

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
