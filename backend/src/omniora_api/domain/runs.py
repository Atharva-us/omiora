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


ACTIVE_STATES = frozenset({RunState.QUEUED, RunState.PLANNING, RunState.AWAITING_APPROVAL})
TERMINAL_STATES = frozenset({RunState.APPROVED, RunState.REJECTED, RunState.FAILED, RunState.CANCELLED})

# `approved` only records consent: in this phase no transition leads to execution.
TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.QUEUED: frozenset({RunState.PLANNING, RunState.CANCELLED, RunState.FAILED}),
    RunState.PLANNING: frozenset({RunState.AWAITING_APPROVAL, RunState.FAILED, RunState.CANCELLED}),
    RunState.AWAITING_APPROVAL: frozenset({RunState.APPROVED, RunState.REJECTED, RunState.QUEUED, RunState.CANCELLED}),
    RunState.APPROVED: frozenset(),
    RunState.REJECTED: frozenset(),
    RunState.FAILED: frozenset(),
    RunState.CANCELLED: frozenset(),
}


def can_transition(current: RunState, target: RunState) -> bool:
    return target in TRANSITIONS[current]


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
