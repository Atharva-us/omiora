"""Run state machine and related finite sets. Mirrored by `src/domain/runs/run.ts`."""

from __future__ import annotations

from enum import StrEnum


class RunState(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting-approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"
    # Requirements Analyst sessions (agent_role "requirements-analyst").
    DISCOVERING = "discovering"
    READY_FOR_REVIEW = "ready-for-review"
    NEEDS_CHANGES = "needs-changes"


class AgentRole(StrEnum):
    PROJECT_MANAGER = "project-manager"
    REQUIREMENTS_ANALYST = "requirements-analyst"


ACTIVE_STATES = frozenset(
    {
        RunState.QUEUED,
        RunState.PLANNING,
        RunState.AWAITING_APPROVAL,
        RunState.DISCOVERING,
        RunState.READY_FOR_REVIEW,
        RunState.NEEDS_CHANGES,
    }
)
TERMINAL_STATES = frozenset({RunState.APPROVED, RunState.REJECTED, RunState.FAILED, RunState.CANCELLED})

# `approved` only records consent: in this phase no transition leads to execution.
PLANNING_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.QUEUED: frozenset({RunState.PLANNING, RunState.CANCELLED, RunState.FAILED}),
    RunState.PLANNING: frozenset({RunState.AWAITING_APPROVAL, RunState.FAILED, RunState.CANCELLED}),
    RunState.AWAITING_APPROVAL: frozenset({RunState.APPROVED, RunState.REJECTED, RunState.QUEUED, RunState.CANCELLED}),
    RunState.APPROVED: frozenset(),
    RunState.REJECTED: frozenset(),
    RunState.FAILED: frozenset(),
    RunState.CANCELLED: frozenset(),
    # A planning run never enters a discovery state.
    RunState.DISCOVERING: frozenset(),
    RunState.READY_FOR_REVIEW: frozenset(),
    RunState.NEEDS_CHANGES: frozenset(),
}


# A discovery session never fails because one turn failed: the turn is marked failed and can be
# retried, and every answer is kept. `failed` is reserved for terminal problems.
DISCOVERY_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.QUEUED: frozenset({RunState.DISCOVERING, RunState.CANCELLED, RunState.FAILED}),
    RunState.DISCOVERING: frozenset({RunState.READY_FOR_REVIEW, RunState.CANCELLED, RunState.FAILED}),
    RunState.READY_FOR_REVIEW: frozenset({RunState.DISCOVERING, RunState.AWAITING_APPROVAL, RunState.CANCELLED}),
    RunState.AWAITING_APPROVAL: frozenset({RunState.APPROVED, RunState.NEEDS_CHANGES, RunState.CANCELLED}),
    RunState.NEEDS_CHANGES: frozenset({RunState.DISCOVERING, RunState.CANCELLED}),
    RunState.APPROVED: frozenset(),
    RunState.FAILED: frozenset(),
    RunState.CANCELLED: frozenset(),
    # A discovery session never enters a planning state.
    RunState.PLANNING: frozenset(),
    RunState.REJECTED: frozenset(),
}

TRANSITIONS_BY_ROLE: dict[AgentRole, dict[RunState, frozenset[RunState]]] = {
    AgentRole.PROJECT_MANAGER: PLANNING_TRANSITIONS,
    AgentRole.REQUIREMENTS_ANALYST: DISCOVERY_TRANSITIONS,
}
TRANSITIONS = PLANNING_TRANSITIONS  # the Project Manager's machine, kept under its original name


def can_transition(current: RunState, target: RunState, role: str = AgentRole.PROJECT_MANAGER) -> bool:
    return target in TRANSITIONS_BY_ROLE[AgentRole(role)][current]


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision-requested"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REVISE = "revise"


DECISION_RESULT: dict[ApprovalDecision, tuple[ApprovalStatus, RunState]] = {
    ApprovalDecision.APPROVE: (ApprovalStatus.APPROVED, RunState.APPROVED),
    ApprovalDecision.REJECT: (ApprovalStatus.REJECTED, RunState.REJECTED),
    ApprovalDecision.REVISE: (ApprovalStatus.REVISION_REQUESTED, RunState.QUEUED),
}


class JobStatus(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AttemptOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    INVALID_OUTPUT = "invalid-output"
    PROVIDER_ERROR = "provider-error"


class RunEventType(StrEnum):
    RUN_CREATED = "run.created"
    STATE_CHANGED = "run.state-changed"
    ATTEMPT_STARTED = "attempt.started"
    ATTEMPT_FINISHED = "attempt.finished"
    PLAN_CREATED = "plan.created"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_DECIDED = "approval.decided"
    # Requirements Analyst sessions.
    TURN_QUEUED = "turn.queued"
    TURN_COMPLETED = "turn.completed"
    TURN_FAILED = "turn.failed"
    ANSWERS_SUBMITTED = "answers.submitted"
    REQUIREMENTS_VERSION_CREATED = "requirements.version-created"


class TurnStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RequirementsDecision(StrEnum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request-changes"
