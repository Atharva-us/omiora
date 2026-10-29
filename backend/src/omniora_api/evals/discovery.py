"""Requirements Analyst evaluation: fixtures and deterministic graders.

Fixtures live in `discovery_fixtures/`. Each holds the persisted state a turn would see (brief,
notes, previous version, questions with answers) and a hand-authored reference output. Graders run
the production validator first, then check structured expectations: readiness, tenancy, question
counts and topics, how "I don't know" answers were handled. The only text check is that a
tenant-isolation requirement's acceptance criteria express denial, with a keyword list fixed in
the fixture before any live run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..agents.requirements_analyst import DiscoveryInput, validate_output
from ..domain.projects import ProjectConfiguration
from ..domain.requirements import QuestionState, RequirementsDocument, tenant_isolation_requirements
from .graders import Grade, _normalise

FIXTURES = Path(__file__).parent / "discovery_fixtures"


@dataclass
class DiscoveryFixture:
    name: str
    description: str
    discovery: DiscoveryInput
    candidate_source: str
    candidate_output: str
    expect: dict[str, Any]


def _input(data: dict[str, Any]) -> DiscoveryInput:
    questions = tuple(
        QuestionState(
            key=q["key"],
            prompt=q["prompt"],
            kind=q["kind"],
            options=tuple(q["options"]),
            blocking=q["blocking"],
            topic=q["topic"],
            status=q["status"],
            unknown=q.get("unknown", False),
        )
        for q in data["questions"]
    )
    return DiscoveryInput(
        configuration=ProjectConfiguration.model_validate(data["configuration"]),
        notes=data["notes"],
        previous=RequirementsDocument.model_validate(data["previous"]) if data["previous"] else None,
        questions=questions,
        answers={
            q["key"]: q["answer"] for q in data["questions"] if q["status"] == "answered" and not q.get("unknown")
        },
        turn=data["turn"],
        max_turns=data["max_turns"],
        final_turn=data.get("final_turn", False),
        first_question_number=len(questions) + 1,
    )


def load_discovery_fixtures() -> list[DiscoveryFixture]:
    fixtures = []
    for path in sorted(FIXTURES.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        output = data["candidate"]["output"]
        fixtures.append(
            DiscoveryFixture(
                name=data["name"],
                description=data["description"],
                discovery=_input(data["input"]),
                candidate_source=data["candidate"]["source"],
                candidate_output=output if isinstance(output, str) else json.dumps(output),
                expect=data["expect"],
            )
        )
    return fixtures


def grade_discovery(fixture: DiscoveryFixture, output: str | None = None) -> Grade:
    text = fixture.candidate_output if output is None else output
    expect = fixture.expect
    parsed, turn, problems = validate_output(text, fixture.discovery)
    result = Grade(fixture=fixture.name, passed=False, problems=problems)

    if not expect["valid"]:
        result.checks["rejected"] = turn is None
        for substring in expect.get("problem_substrings", []):
            result.checks[f"problem:{substring}"] = any(substring in p for p in problems)
        result.passed = all(result.checks.values())
        return result

    result.checks["valid"] = turn is not None
    if parsed is None or turn is None or turn.document is None:
        return result
    document = turn.document
    questions = parsed.questions
    blocking = [q for q in questions if q.blocking]

    if "ready" in expect:
        result.checks[f"ready={expect['ready']}"] = document.readiness.ready == expect["ready"]
    if "tenancy" in expect:
        result.checks[f"tenancy={expect['tenancy']}"] = document.context.tenancy == expect["tenancy"]
    if "max_questions" in expect:
        result.checks[f"questions<={expect['max_questions']}"] = len(questions) <= expect["max_questions"]
    if "min_blocking_questions" in expect:
        minimum = expect["min_blocking_questions"]
        result.checks[f"blocking_questions>={minimum}"] = len(blocking) >= minimum
    if "max_blocking_questions" in expect:
        maximum = expect["max_blocking_questions"]
        result.checks[f"blocking_questions<={maximum}"] = len(blocking) <= maximum
    if "question_topics" in expect:
        asked = {q.topic for q in questions}
        for topic in expect["question_topics"]:
            result.checks[f"asks:{topic}"] = topic in asked
    if "blocking_question_topics" in expect:
        topics = set(expect["blocking_question_topics"])
        result.checks["blocking_question_on_" + "/".join(sorted(topics))] = any(q.topic in topics for q in blocking)
    if "max_active_requirements" in expect:
        maximum = expect["max_active_requirements"]
        result.checks[f"active_requirements<={maximum}"] = len(document.active()) <= maximum
    if "isolation_criteria_keywords" in expect:
        keywords = [_normalise(k) for k in expect["isolation_criteria_keywords"]]
        criteria = [_normalise(c) for r in tenant_isolation_requirements(document) for c in r.acceptance_criteria]
        result.checks["isolation_criteria_prove_denial"] = any(k in c for c in criteria for k in keywords)
    for key in expect.get("unknown_handled", []):
        assumed = any(key in a.basis and a.confidence == "low" for a in document.assumptions)
        still_open = not document.readiness.ready and any(q.key == key for q in document.open_questions)
        cited_as_fact = any(f"answer:{key}" in r.evidence and r.source == "answer" for r in document.active())
        result.checks[f"unknown_handled:{key}"] = (assumed or still_open) and not cited_as_fact

    result.passed = all(result.checks.values())
    return result
