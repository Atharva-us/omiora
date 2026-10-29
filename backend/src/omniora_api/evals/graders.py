from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..agents.project_manager import validate_output
from ..domain.plans import ProjectPlan, find_cycle
from ..domain.projects import ProjectConfiguration

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass
class Fixture:
    name: str
    description: str
    configuration: ProjectConfiguration
    notes: list[str]
    candidate_source: str
    candidate_output: str
    expect: dict[str, Any]


@dataclass
class Grade:
    fixture: str
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def load_fixtures() -> list[Fixture]:
    fixtures = []
    for path in sorted(FIXTURES.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        output = data["candidate"]["output"]
        fixtures.append(
            Fixture(
                name=data["name"],
                description=data["description"],
                configuration=ProjectConfiguration.model_validate(data["input"]["configuration"]),
                notes=data["input"]["notes"],
                candidate_source=data["candidate"]["source"],
                candidate_output=output if isinstance(output, str) else json.dumps(output),
                expect=data["expect"],
            )
        )
    return fixtures


# Models often write typographic hyphens (U+2010-U+2015, U+2212); fold them so "sign-in" matches.
_HYPHENS = str.maketrans({code: "-" for code in (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2212)})


def _normalise(text: str) -> str:
    return text.translate(_HYPHENS).lower()


def _plan_text(plan: ProjectPlan) -> str:
    parts = [plan.summary, *plan.assumptions]
    parts += [r.statement for r in plan.requirements]
    parts += [f"{t.title} {t.description} {' '.join(t.acceptance_criteria)}" for t in plan.tasks]
    return _normalise(" ".join(parts))


def _has_topic(text: str, keywords: list[str]) -> bool:
    return any(_normalise(keyword) in text for keyword in keywords)


def grade(fixture: Fixture, output: str | None = None) -> Grade:
    """Grades `output` (defaults to the fixture's candidate) against the fixture's expectations."""
    text = fixture.candidate_output if output is None else output
    expect = fixture.expect
    plan, problems = validate_output(text, fixture.configuration)
    result = Grade(fixture=fixture.name, passed=False, problems=problems)

    if not expect["valid"]:
        result.checks["rejected"] = plan is None
        for substring in expect.get("problem_substrings", []):
            result.checks[f"problem:{substring}"] = any(substring in p for p in problems)
        result.passed = all(result.checks.values())
        return result

    result.checks["structurally_valid"] = plan is not None
    if plan is None:
        return result

    dependencies = {task.key: task.depends_on for task in plan.tasks}
    result.checks["dependencies_acyclic"] = find_cycle(dependencies) is None
    result.checks["dependencies_resolve"] = all(d in dependencies for deps in dependencies.values() for d in deps)

    body = _plan_text(plan)
    for topic in expect.get("coverage", []):
        result.checks[f"covers:{topic['topic']}"] = _has_topic(body, topic["keywords"])

    questions = _normalise(" ".join(f"{q.question} {q.why_it_matters}" for q in plan.open_questions))
    for topic in expect.get("questions", []):
        result.checks[f"asks:{topic['topic']}"] = _has_topic(questions, topic["keywords"])
    minimum = expect.get("min_blocking_questions", 0)
    if minimum:
        result.checks[f"blocking_questions>={minimum}"] = sum(q.blocking for q in plan.open_questions) >= minimum

    result.passed = all(result.checks.values())
    return result
