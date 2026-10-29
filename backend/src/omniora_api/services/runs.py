"""Planning run use cases: start, read, cancel, and approval decisions.

Every state change happens under the run's row lock, is validated against the state machine, and
appends its run event in the same transaction. Commands that a client may retry (start, cancel,
approval decisions) are idempotent.

Planning normally starts from the project's latest approved requirements (Agent 2), and the run is
pinned to that exact version. Planning without requirements is a separate, explicit choice that
is recorded on the run (`requirements_skipped`); it is never a silent fallback.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError

from ..audit import append_audit
from ..db.models import AgentAttempt, Approval, EngineeringTask, PlanVersion, RequirementsVersion, Run, RunEvent
from ..db.session import SessionFactory, transaction
from ..domain.runs import (
    DECISION_RESULT,
    TERMINAL_STATES,
    ApprovalDecision,
    ApprovalStatus,
    RunEventType,
    RunState,
    can_transition,
)
from ..errors import ApiError
from ..repositories import projects as projects_repo
from ..repositories import requirements as requirements_repo
from ..repositories import runs as repo
from . import Clock, utcnow
from .projects import parse_project_id

PLAN_JOB = "plan"
AGENT_ROLE = "project-manager"


@dataclass(frozen=True)
class RunDetail:
    run: Run
    plan: PlanVersion | None
    tasks: list[EngineeringTask]
    approvals: list[Approval]
    attempts: list[AgentAttempt]
    requirements: RequirementsVersion | None = None  # the pinned approved version, if any


def plan_job_key(run_id: uuid.UUID, version: int) -> str:
    return f"{PLAN_JOB}:{run_id}:v{version}"


def transition(session, run: Run, target: RunState, now, data: dict[str, Any] | None = None) -> None:
    """Caller holds the run lock. Raises if the state machine forbids the move."""
    current = RunState(run.state)
    if not can_transition(current, target, run.agent_role):
        raise ApiError("conflict", f"This run cannot move from {current.value} to {target.value}.")
    run.state = target.value
    run.updated_at = now
    repo.append_event(
        session, run, RunEventType.STATE_CHANGED, {"from": current.value, "to": target.value, **(data or {})}, now
    )


class RunsService:
    def __init__(
        self,
        factory: SessionFactory,
        *,
        runs_per_user_per_hour: int,
        job_max_deliveries: int,
        provider_configured: bool,
        clock: Clock = utcnow,
    ) -> None:
        self._factory = factory
        self._hourly_limit = runs_per_user_per_hour
        self._max_deliveries = job_max_deliveries
        self._provider_configured = provider_configured
        self._clock = clock

    def start(
        self, user_id: uuid.UUID, project_id: str, idempotency_key: str, *, without_requirements: bool = False
    ) -> tuple[Run, bool]:
        """Returns (run, created). Repeating a key returns the original run without side effects."""
        pid = parse_project_id(project_id)
        with transaction(self._factory) as session:
            project = projects_repo.get_owned_project(session, pid, user_id, lock=True)
            if project is None:
                raise ApiError("not-found", "This project no longer exists.")
            existing = repo.get_run_by_idempotency_key(session, project.id, idempotency_key)
            if existing is not None:
                if existing.agent_role != AGENT_ROLE:
                    raise ApiError("conflict", "This idempotency key was already used for a different request.")
                return existing, False
            approved = None if without_requirements else requirements_repo.latest_approved_for_project(session, pid)
            if approved is None and not without_requirements:
                raise ApiError(
                    "conflict",
                    "Approve the project's requirements with the Requirements Analyst first, or explicitly choose "
                    "to plan without requirements.",
                )
            if not self._provider_configured:
                raise ApiError(
                    "provider-not-configured",
                    "Planning is unavailable: no model provider is configured on the server. "
                    "An operator must set the selected provider's key (ANTHROPIC_API_KEY or GROQ_API_KEY) "
                    "for the backend and worker.",
                )
            now = self._clock()
            if repo.count_runs_created_since(session, user_id, now - timedelta(hours=1)) >= self._hourly_limit:
                raise ApiError(
                    "rate-limited",
                    "You have started too many planning runs in the last hour. Try again later.",
                    headers={"Retry-After": "3600"},
                )
            run = Run(
                project_id=project.id,
                created_by=user_id,
                agent_role=AGENT_ROLE,
                state=RunState.QUEUED.value,
                idempotency_key=idempotency_key,
                pinned_requirements_version_id=approved.id if approved else None,
                requirements_skipped=without_requirements,
                created_at=now,
                updated_at=now,
            )
            session.add(run)
            try:
                session.flush()  # the project row lock serialises starts, but the partial unique index is the guarantee
            except IntegrityError:
                session.rollback()
                raise ApiError(
                    "conflict", "Another run (planning or requirements discovery) is in progress for this project."
                ) from None
            basis = (
                {"requirements_version_id": str(approved.id), "requirements_version": approved.version}
                if approved
                else {"requirements_skipped": True}
            )
            repo.append_event(session, run, RunEventType.RUN_CREATED, {"agent": AGENT_ROLE, **basis}, now)
            repo.add_job(
                session,
                run_id=run.id,
                kind=PLAN_JOB,
                payload={"version": 1},
                dedupe_key=plan_job_key(run.id, 1),
                max_deliveries=self._max_deliveries,
                now=now,
            )
            append_audit(
                session,
                actor_type="user",
                actor_id=str(user_id),
                action="run.started",
                entity_type="run",
                entity_id=str(run.id),
                data={"project_id": str(project.id), **basis},
            )
            return run, True

    def list_for_project(self, user_id: uuid.UUID, project_id: str) -> list[Run]:
        try:
            pid = parse_project_id(project_id)
        except ApiError as error:
            if error.code == "read-only":
                return []  # samples never have runs
            raise
        with transaction(self._factory) as session:
            if projects_repo.get_owned_project(session, pid, user_id) is None:
                raise ApiError("not-found", "This project no longer exists.")
            return repo.list_project_runs(session, pid, AGENT_ROLE)

    def _require(
        self, session, user_id: uuid.UUID, run_id: uuid.UUID, *, lock: bool = False, planning: bool = False
    ) -> Run:
        run = repo.get_run_for_owner(session, run_id, user_id, lock=lock)
        if run is None:
            raise ApiError("not-found", "This run does not exist.")
        if planning and run.agent_role != AGENT_ROLE:
            raise ApiError("conflict", "This is a requirements session; use the requirements session endpoints.")
        return run

    def detail(self, user_id: uuid.UUID, run_id: uuid.UUID) -> RunDetail:
        with transaction(self._factory) as session:
            run = self._require(session, user_id, run_id)
            plan = (
                repo.get_plan_version(session, run.id, run.current_plan_version) if run.current_plan_version else None
            )
            tasks = repo.list_tasks(session, run.id, run.current_plan_version) if run.current_plan_version else []
            pinned = (
                requirements_repo.get_version_by_id(session, run.pinned_requirements_version_id)
                if run.pinned_requirements_version_id
                else None
            )
            return RunDetail(
                run, plan, tasks, repo.list_approvals(session, run.id), repo.list_attempts(session, run.id), pinned
            )

    def authorize(self, user_id: uuid.UUID, run_id: uuid.UUID) -> Run:
        with transaction(self._factory) as session:
            return self._require(session, user_id, run_id)

    def cancel(self, user_id: uuid.UUID, run_id: uuid.UUID) -> Run:
        now = self._clock()
        with transaction(self._factory) as session:
            run = self._require(session, user_id, run_id, lock=True, planning=True)
            if run.state == RunState.CANCELLED:
                return run  # idempotent
            if RunState(run.state) in TERMINAL_STATES:
                raise ApiError("conflict", f"This run already finished ({run.state}) and cannot be cancelled.")
            transition(session, run, RunState.CANCELLED, now)
            repo.close_pending_approvals(session, run.id, ApprovalStatus.CANCELLED, now)
            repo.cancel_open_jobs(session, run.id)
            append_audit(
                session,
                actor_type="user",
                actor_id=str(user_id),
                action="run.cancelled",
                entity_type="run",
                entity_id=str(run.id),
            )
            return run

    def decide(
        self,
        user_id: uuid.UUID,
        run_id: uuid.UUID,
        approval_id: uuid.UUID,
        *,
        decision: ApprovalDecision,
        plan_version: int,
        comment: str | None,
    ) -> Approval:
        comment = (comment or "").strip() or None
        if decision == ApprovalDecision.REVISE and not comment:
            raise ApiError("validation", "Describe what should change when requesting a revision.")
        now = self._clock()
        with transaction(self._factory) as session:
            run = self._require(session, user_id, run_id, lock=True, planning=True)
            approval = repo.get_approval(session, run.id, approval_id, lock=True)
            if approval is None or approval.gate != "plan":
                raise ApiError("not-found", "This approval request does not exist.")
            if approval.plan_version != plan_version:
                raise ApiError(
                    "conflict", "This approval is for a different plan version. Reload the plan and decide again."
                )
            target_status, target_state = DECISION_RESULT[decision]
            if approval.status != ApprovalStatus.PENDING:
                if approval.status == target_status:
                    return approval  # the same decision submitted twice: idempotent
                if approval.status == ApprovalStatus.SUPERSEDED:
                    raise ApiError("conflict", "A newer plan version replaced this one. Review the latest plan.")
                raise ApiError("conflict", f"This plan was already {approval.status.replace('-', ' ')}.")
            if run.current_plan_version != plan_version:
                raise ApiError("conflict", "This approval is for a plan that is no longer current.")

            approval.status = target_status.value
            approval.decided_by = user_id
            approval.decided_at = now
            approval.comment = comment
            repo.append_event(
                session,
                run,
                RunEventType.APPROVAL_DECIDED,
                {"approval_id": str(approval.id), "decision": decision.value, "plan_version": plan_version},
                now,
            )
            transition(session, run, target_state, now)
            if decision == ApprovalDecision.REVISE:
                next_version = plan_version + 1
                repo.add_job(
                    session,
                    run_id=run.id,
                    kind=PLAN_JOB,
                    payload={"version": next_version, "revision_comment": comment},
                    dedupe_key=plan_job_key(run.id, next_version),
                    max_deliveries=self._max_deliveries,
                    now=now,
                )
            # Approval only records consent. Nothing is executed in this phase.
            append_audit(
                session,
                actor_type="user",
                actor_id=str(user_id),
                action=f"plan.{decision.value}",
                entity_type="run",
                entity_id=str(run.id),
                data={"plan_version": plan_version},
            )
            return approval

    def events(self, run_id: uuid.UUID, after_seq: int, limit: int = 200) -> tuple[list[RunEvent], str]:
        """Events after `after_seq` plus the run's current state. Authorisation is checked by the caller."""
        with transaction(self._factory) as session:
            run = repo.get_run(session, run_id)
            if run is None:
                return [], RunState.CANCELLED.value
            return repo.list_events(session, run_id, after_seq, limit), run.state
