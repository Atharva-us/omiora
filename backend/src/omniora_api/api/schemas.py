"""Transport schemas. JSON uses camelCase to match the frontend's Zod schemas
(`src/domain/projects/project.ts`, `src/domain/runs/run.ts`)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ..domain.projects import ProjectConfiguration
from ..domain.runs import ApprovalDecision, RequirementsDecision


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
    pinned_requirements_version_id: str | None
    requirements_skipped: bool
    created_at: str
    updated_at: str


class StartRunIn(RequestModel):
    # Planning normally follows the project's approved requirements. True is the explicit,
    # recorded choice to plan without them.
    without_requirements: bool = False


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


class FlaggedRequirementOut(ApiModel):
    id: str
    reason: str


class PlanContentOut(ApiModel):
    summary: str
    requirements: list[PlanRequirementOut]
    assumptions: list[str]
    open_questions: list[OpenQuestionOut]
    recommended_stack: RecommendedStackOut
    required_approvals: list[RequiredApprovalOut]
    flagged_requirements: list[FlaggedRequirementOut] = Field(default_factory=list)  # absent on older plans


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


class PinnedRequirementsOut(ApiModel):
    version_id: str
    session_id: str
    version: int
    content_sha256: str


class RunDetailOut(ApiModel):
    run: RunOut
    plan: PlanOut | None
    tasks: list[TaskOut]
    approvals: list[ApprovalOut]
    attempts: list[AttemptOut]
    requirements: PinnedRequirementsOut | None


class DecisionIn(RequestModel):
    decision: ApprovalDecision
    plan_version: int = Field(ge=1)
    comment: str | None = Field(default=None, max_length=2000)


class RunEventOut(ApiModel):
    seq: int
    type: str
    data: dict[str, Any]
    at: str


# --- requirements analyst -----------------------------------------------------------------

AnswerText = Annotated[str, Field(max_length=2000)]
OptionText = Annotated[str, Field(max_length=200)]


class AnswerIn(RequestModel):
    question_key: str = Field(pattern=r"^DQ-\d{3,6}$")
    value: AnswerText | Annotated[list[OptionText], Field(max_length=8)] | bool | None = None
    unknown: bool = False  # "I don't know": recorded as unknown, never as a fact


class AnswersIn(RequestModel):
    answers: list[AnswerIn] = Field(default_factory=list, max_length=20)
    advance: bool = False  # ask the analyst for the next turn after saving


class SubmitIn(RequestModel):
    version: int = Field(ge=1, le=100_000)


class RequirementsDecisionIn(RequestModel):
    decision: RequirementsDecision
    version: int = Field(ge=1, le=100_000)
    comment: str | None = Field(default=None, max_length=2000)


class PersonaOut(ApiModel):
    name: str
    description: str


class ProjectContextOut(ApiModel):
    goal: str
    scope: str
    platform: str
    deployment: str
    personas: list[PersonaOut]
    tenancy: str
    constraints: list[str]
    integrations: list[str]
    out_of_scope: list[str]


class RequirementOut(ApiModel):
    id: str
    statement: str
    kind: str
    priority: str
    confidence: str
    source: str
    evidence: list[str]
    acceptance_criteria: list[str]
    tags: list[str]
    status: str
    deprecation_reason: str


class AssumptionOut(ApiModel):
    statement: str
    confidence: str
    basis: list[str]


class OpenQuestionRefOut(ApiModel):
    key: str
    prompt: str
    blocking: bool
    topic: str
    status: str


class ReadinessOut(ApiModel):
    ready: bool
    blockers: list[str]


class RequirementsDocumentOut(ApiModel):
    schema_version: int
    context: ProjectContextOut
    requirements: list[RequirementOut]
    assumptions: list[AssumptionOut]
    open_questions: list[OpenQuestionRefOut]
    readiness: ReadinessOut
    decisions: list[str]


class RequirementChangeOut(ApiModel):
    id: str
    fields: list[str]


class VersionDiffOut(ApiModel):
    from_version: int
    added: list[str]
    deprecated: list[str]
    changed: list[RequirementChangeOut]
    context_fields: list[str]


class RequirementsVersionSummaryOut(ApiModel):
    id: str
    version: int
    parent_version_id: str | None
    content_sha256: str
    turn_number: int | None
    created_at: str
    frozen_at: str | None
    approved_at: str | None
    requirement_count: int
    must_count: int
    ready: bool


class RequirementsVersionOut(RequirementsVersionSummaryOut):
    content: RequirementsDocumentOut
    diff: VersionDiffOut | None = None


class TurnOut(ApiModel):
    number: int
    status: str
    trigger: str
    tries: int
    failure_code: str | None
    failure_message: str | None
    requirements_version: int | None
    created_at: str
    completed_at: str | None


class AnswerOut(ApiModel):
    value: Any
    unknown: bool
    answered_at: str


class QuestionOut(ApiModel):
    key: str
    turn_number: int
    prompt: str
    why: str
    kind: str
    options: list[str]
    blocking: bool
    topic: str
    relates_to: list[str]
    status: str
    answer: AnswerOut | None


class RequirementsApprovalOut(ApiModel):
    id: str
    version: int
    gate: str
    status: str
    comment: str | None
    decided_at: str | None
    created_at: str


class TurnAttemptOut(ApiModel):
    turn: int
    attempt: int
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


class RequirementsSessionOut(ApiModel):
    id: str
    project_id: str
    state: str
    failure_code: str | None
    failure_message: str | None
    last_event_seq: int
    created_at: str
    updated_at: str


class RequirementsSessionDetailOut(ApiModel):
    session: RequirementsSessionOut
    turn: TurnOut | None
    max_turns: int
    questions: list[QuestionOut]
    version: RequirementsVersionOut | None
    approvals: list[RequirementsApprovalOut]
    attempts: list[TurnAttemptOut]


class ApprovedRequirementsOut(ApiModel):
    session_id: str
    version: RequirementsVersionOut
