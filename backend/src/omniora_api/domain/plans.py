"""The Project Manager agent's output contract and its semantic validation.

Validation has two layers:
1. Shape: `ProjectPlan` (Pydantic, `extra="forbid"`, bounded sizes).
2. Semantics: `plan_problems()` checks things a schema cannot express: unique ids, resolvable
   references, an acyclic dependency graph, requirement coverage, and stack rules.
A plan is accepted only if both pass.
"""

from __future__ import annotations

from collections import deque
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .projects import CustomStack, ProjectConfiguration, TechnologyId, validate_technologies

# Agents 2-10. The Project Manager never assigns work to itself.
FutureAgentRole = Literal[
    "requirements-analyst",
    "reference-design",
    "software-architect",
    "frontend-engineer",
    "backend-engineer",
    "mobile-engineer",
    "database-engineer",
    "qa-debugging",
    "security-release",
]
FUTURE_AGENT_ROLES: tuple[str, ...] = FutureAgentRole.__args__  # type: ignore[attr-defined]

Key = str  # short stable identifiers such as "R1" or "T3"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanRequirement(_Strict):
    id: Key = Field(min_length=1, max_length=16)
    statement: str = Field(min_length=1, max_length=500)
    kind: Literal["functional", "non-functional", "constraint"]
    priority: Literal["must", "should", "could"]
    source: Literal["user", "inferred"]


class OpenQuestion(_Strict):
    id: Key = Field(min_length=1, max_length=16)
    question: str = Field(min_length=1, max_length=500)
    why_it_matters: str = Field(min_length=1, max_length=500)
    blocking: bool


class RecommendedStack(_Strict):
    technologies: list[TechnologyId] = Field(max_length=7)
    rationale: str = Field(max_length=1000)


class PlanTask(_Strict):
    key: Key = Field(min_length=1, max_length=16)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=10)
    depends_on: list[Key] = Field(max_length=20)
    requirement_ids: list[Key] = Field(min_length=1, max_length=20)
    suggested_agent: FutureAgentRole


class RequiredApproval(_Strict):
    gate: Literal["plan", "architecture", "release"]
    description: str = Field(min_length=1, max_length=500)


class ProjectPlan(_Strict):
    summary: str = Field(min_length=1, max_length=2000)
    requirements: list[PlanRequirement] = Field(min_length=1, max_length=50)
    assumptions: list[str] = Field(max_length=30)
    open_questions: list[OpenQuestion] = Field(max_length=20)
    recommended_stack: RecommendedStack
    tasks: list[PlanTask] = Field(min_length=1, max_length=40)
    required_approvals: list[RequiredApproval] = Field(min_length=1, max_length=5)


def _string_array() -> dict[str, object]:
    return {"type": "array", "items": {"type": "string"}}


def _object(properties: dict[str, object]) -> dict[str, object]:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def plan_output_schema() -> dict[str, object]:
    """JSON Schema sent to the provider's structured-output feature.

    Deliberately limited to widely supported keywords (types, enums, required,
    additionalProperties). Length and count limits are enforced afterwards by `ProjectPlan`.
    """
    technology_ids = list(TechnologyId.__args__)  # type: ignore[attr-defined]
    return _object(
        {
            "summary": {"type": "string"},
            "requirements": {
                "type": "array",
                "items": _object(
                    {
                        "id": {"type": "string"},
                        "statement": {"type": "string"},
                        "kind": {"type": "string", "enum": ["functional", "non-functional", "constraint"]},
                        "priority": {"type": "string", "enum": ["must", "should", "could"]},
                        "source": {"type": "string", "enum": ["user", "inferred"]},
                    }
                ),
            },
            "assumptions": _string_array(),
            "open_questions": {
                "type": "array",
                "items": _object(
                    {
                        "id": {"type": "string"},
                        "question": {"type": "string"},
                        "why_it_matters": {"type": "string"},
                        "blocking": {"type": "boolean"},
                    }
                ),
            },
            "recommended_stack": _object(
                {
                    "technologies": {"type": "array", "items": {"type": "string", "enum": technology_ids}},
                    "rationale": {"type": "string"},
                }
            ),
            "tasks": {
                "type": "array",
                "items": _object(
                    {
                        "key": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "acceptance_criteria": _string_array(),
                        "depends_on": _string_array(),
                        "requirement_ids": _string_array(),
                        "suggested_agent": {"type": "string", "enum": list(FUTURE_AGENT_ROLES)},
                    }
                ),
            },
            "required_approvals": {
                "type": "array",
                "items": _object(
                    {
                        "gate": {"type": "string", "enum": ["plan", "architecture", "release"]},
                        "description": {"type": "string"},
                    }
                ),
            },
        }
    )


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def find_cycle(dependencies: dict[str, list[str]]) -> list[str] | None:
    """Kahn's algorithm. Returns the keys left on a cycle (sorted), or None if acyclic."""
    indegree = {key: 0 for key in dependencies}
    dependents: dict[str, list[str]] = {key: [] for key in dependencies}
    for key, deps in dependencies.items():
        for dep in deps:
            if dep in dependencies:
                indegree[key] += 1
                dependents[dep].append(key)
    queue = deque(key for key, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        key = queue.popleft()
        visited += 1
        for dependent in dependents[key]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)
    if visited == len(dependencies):
        return None
    return sorted(key for key, degree in indegree.items() if degree > 0)


def plan_problems(plan: ProjectPlan, configuration: ProjectConfiguration) -> list[str]:
    """Semantic problems with a shape-valid plan. Empty means the plan is acceptable."""
    problems: list[str] = []
    task_keys = [task.key for task in plan.tasks]
    requirement_ids = [requirement.id for requirement in plan.requirements]

    for label, values in (
        ("task key", task_keys),
        ("requirement id", requirement_ids),
        ("question id", [q.id for q in plan.open_questions]),
    ):
        for duplicate in _duplicates(values):
            problems.append(f"Duplicate {label} {duplicate!r}.")

    known_tasks = set(task_keys)
    known_requirements = set(requirement_ids)
    for task in plan.tasks:
        if task.key in task.depends_on:
            problems.append(f"Task {task.key!r} depends on itself.")
        for dep in task.depends_on:
            if dep not in known_tasks:
                problems.append(f"Task {task.key!r} depends on unknown task {dep!r}.")
        for requirement_id in task.requirement_ids:
            if requirement_id not in known_requirements:
                problems.append(f"Task {task.key!r} references unknown requirement {requirement_id!r}.")

    cycle = find_cycle({task.key: [d for d in task.depends_on if d != task.key] for task in plan.tasks})
    if cycle:
        problems.append(f"Task dependencies contain a cycle involving {', '.join(cycle)}.")

    covered = {requirement_id for task in plan.tasks for requirement_id in task.requirement_ids}
    for requirement in plan.requirements:
        if requirement.priority == "must" and requirement.id not in covered:
            problems.append(f"Must-have requirement {requirement.id!r} is not covered by any task.")

    stack = plan.recommended_stack
    if isinstance(configuration.stack, CustomStack):
        if stack.technologies:
            problems.append("A stack was chosen by the user, so recommended_stack.technologies must be empty.")
    else:
        if not stack.technologies:
            problems.append("The user asked for a recommendation, so recommended_stack.technologies is required.")
        elif not stack.rationale.strip():
            problems.append("recommended_stack.rationale is required when technologies are recommended.")
        else:
            problems.extend(
                f"Recommended stack: {error}"
                for error in validate_technologies(configuration.platform, list(stack.technologies)).errors
            )

    if not any(approval.gate == "plan" for approval in plan.required_approvals):
        problems.append("required_approvals must include the 'plan' gate.")
    return problems
