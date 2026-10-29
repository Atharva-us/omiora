"""Transport schemas. JSON uses camelCase to match the frontend's Zod schemas
(`src/domain/projects/project.ts`, `src/domain/runs/run.ts`)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ..domain.projects import ProjectConfiguration
from ..domain.runs import ApprovalDecision


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class RequestModel(ApiModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


def iso(value: datetime) -> str:
    """UTC ISO-8601 with milliseconds and `Z`, the format the frontend's `z.iso.datetime()` accepts."""
    utc = value.astimezone(UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"


# --- auth ---------------------------------------------------------------------------------


class RegisterIn(RequestModel):
    name: str = Field(max_length=200)
    email: str = Field(max_length=400)
    password: str = Field(max_length=1024)


class SignInIn(RequestModel):
    email: str = Field(max_length=400)
    password: str = Field(max_length=1024)


class PasswordResetIn(RequestModel):
    email: str = Field(max_length=400)


class AuthUserOut(ApiModel):
    id: str
    email: str
    name: str


# --- projects -----------------------------------------------------------------------------


class ProjectOut(ApiModel):
    id: str
    source: Literal["user", "sample"]
    status: str
    configuration: dict[str, Any]
    created_at: str
    updated_at: str


class ProjectPageOut(ApiModel):
    items: list[ProjectOut]
    next_cursor: str | None


class ProjectUpdateIn(RequestModel):
    name: str | None = Field(default=None, max_length=400)
    configuration: ProjectConfiguration | None = None


class NoteIn(RequestModel):
    content: str = Field(max_length=4000)


class NoteOut(ApiModel):
    id: str
    content: str
    at: str


class HistoryOut(ApiModel):
    id: str
    project_id: str
    at: str
    summary: str


# --- runs ---------------------------------------------------------------------------------


class RunOut(ApiModel):
    id: str
    project_id: str
    agent_role: str
    state: str
    current_plan_version: int | None
    failure_code: str | None
    failure_message: str | None
    last_event_seq: int
    created_at: str
    updated_at: str


class PlanRequirementOut(ApiModel):
    id: str
    statement: str
    kind: str
    priority: str
    source: str


class OpenQuestionOut(ApiModel):
    id: str
    question: str
    why_it_matters: str
    blocking: bool


class RecommendedStackOut(ApiModel):
    technologies: list[str]
    rationale: str


class RequiredApprovalOut(ApiModel):
    gate: str
    description: str


class PlanContentOut(ApiModel):
    summary: str
    requirements: list[PlanRequirementOut]
    assumptions: list[str]
    open_questions: list[OpenQuestionOut]
    recommended_stack: RecommendedStackOut
    required_approvals: list[RequiredApprovalOut]


class PlanOut(ApiModel):
    version: int
    created_at: str
    content: PlanContentOut


class TaskOut(ApiModel):
    key: str
    title: str
    description: str
    acceptance_criteria: list[str]
    depends_on: list[str]
    requirement_ids: list[str]
    suggested_agent: str
    status: Literal["proposed"]


class ApprovalOut(ApiModel):
    id: str
    plan_version: int
    gate: str
    status: str
    comment: str | None
    decided_at: str | None
    created_at: str


class AttemptOut(ApiModel):
    attempt: int
    plan_version: int
    outcome: str
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int | None
    error_code: str | None
    error_message: str | None
    validation_errors: list[str]
    created_at: str


class RunDetailOut(ApiModel):
    run: RunOut
    plan: PlanOut | None
    tasks: list[TaskOut]
    approvals: list[ApprovalOut]
    attempts: list[AttemptOut]


class DecisionIn(RequestModel):
    decision: ApprovalDecision
    plan_version: int = Field(ge=1)
    comment: str | None = Field(default=None, max_length=2000)


class RunEventOut(ApiModel):
    seq: int
    type: str
    data: dict[str, Any]
    at: str
