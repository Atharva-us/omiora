"""Handler for `plan` jobs: runs the Project Manager agent and commits the outcome.

Commit protocol (what makes duplicate delivery safe):
1. Claim and start: run `queued → planning` (or continue if a previous delivery already did).
2. Model attempts run outside any transaction; each finished attempt is persisted immediately.
3. Final transaction: lock the run, then mark the job done *only if this worker still holds a valid
   lease*. If not (the lease expired and the job was re-delivered), everything rolls back and the
   result is discarded. A unique (run_id, version) constraint on plan versions is a second guard.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass

from ..agents.project_manager import AttemptRecord, PlanningInput, run_project_manager
from ..audit import append_audit
from ..config import Settings
from ..db.models import EngineeringTask, Project
from ..db.session import SessionFactory, transaction
from ..domain.projects import ProjectConfiguration
from ..domain.runs import ApprovalStatus, JobStatus, RunEventType, RunState
from ..llm.base import ModelProvider
from ..repositories import projects as projects_repo
from ..repositories import runs as repo
from ..services import Clock, utcnow
from ..services.runs import transition

logger = logging.getLogger("omniora.worker.planning")


@dataclass(frozen=True)
class JobSnapshot:
    id: uuid.UUID
    run_id: uuid.UUID
    payload: dict
    deliveries: int


class LeaseState:
    """Shared between the handler and the lease keeper thread."""

    def __init__(self) -> None:
        self._lost = threading.Event()

    def mark_lost(self) -> None:
        self._lost.set()

    @property
    def lost(self) -> bool:
        return self._lost.is_set()


class _LostLease(Exception):
    pass


class PlanningJobHandler:
    def __init__(
        self, factory: SessionFactory, provider: ModelProvider, settings: Settings, clock: Clock = utcnow
    ) -> None:
        self._factory = factory
        self._provider = provider
        self._settings = settings
        self._clock = clock

    def handle(self, job: JobSnapshot, owner: str, lease: LeaseState) -> str:
        version = int(job.payload.get("version", 1))
        planning_input = self._start(job, owner, version)
        if planning_input is None:
            return "skipped"

        attempt_ids: dict[int, uuid.UUID] = {}

        def before_attempt(number: int) -> bool:
            if lease.lost:
                return False
            now = self._clock()
            with transaction(self._factory) as session:
                run = repo.get_run(session, job.run_id, lock=True)
                if run is None or run.state != RunState.PLANNING:
                    return False
                repo.append_event(
                    session, run, RunEventType.ATTEMPT_STARTED, {"attempt": number, "plan_version": version}, now
                )
            return True

        def on_attempt(record: AttemptRecord) -> None:
            now = self._clock()
            with transaction(self._factory) as session:
                attempt = repo.add_attempt(
                    session,
                    run_id=job.run_id,
                    job_id=job.id,
                    plan_version=version,
                    attempt=record.attempt,
                    outcome=record.outcome,
                    provider=record.provider,
                    model=record.model,
                    input_tokens=record.input_tokens,
                    output_tokens=record.output_tokens,
                    latency_ms=record.latency_ms,
                    request_id=record.request_id,
                    error_code=record.error_code,
                    error_message=record.error_message,
                    validation_errors=record.validation_errors,
                    raw_output=record.raw_output,
                    prompt_sha256=record.prompt_sha256,
                    created_at=now,
                )
                attempt_ids[record.attempt] = attempt.id
                run = repo.get_run(session, job.run_id, lock=True)
                if run is not None:
                    repo.append_event(
                        session,
                        run,
                        RunEventType.ATTEMPT_FINISHED,
                        {
                            "attempt": record.attempt,
                            "outcome": record.outcome,
                            "error_code": record.error_code,
                            "problem_count": len(record.validation_errors),
                        },
                        now,
                    )

        result = run_project_manager(
            self._provider,
            planning_input,
            max_attempts=self._settings.pm_max_attempts,
            max_output_tokens=self._settings.planning_max_output_tokens,
            effort=self._settings.planning_effort,
            timeout_seconds=self._settings.model_timeout_seconds,
            before_attempt=before_attempt,
            on_attempt=on_attempt,
        )

        try:
            return self._commit(job, owner, version, result, attempt_ids)
        except _LostLease:
            logger.warning("planning result discarded: lease lost", extra={"job_id": str(job.id)})
            return "lost-lease"

    def _start(self, job: JobSnapshot, owner: str, version: int) -> PlanningInput | None:
        now = self._clock()
        with transaction(self._factory) as session:
            run = repo.get_run(session, job.run_id, lock=True)
            if run is None or run.state not in (RunState.QUEUED, RunState.PLANNING):
                # Cancelled or already finished: retire the job without doing any work.
                repo.finish_job_if_owner(session, job.id, owner, JobStatus.CANCELLED, now)
                return None
            if run.state == RunState.QUEUED:
                transition(session, run, RunState.PLANNING, now, {"plan_version": version})
            project = session.get(Project, run.project_id)
            if project is None:
                return None
            notes = [note.content for note in projects_repo.list_notes(session, project.id)]
            previous = repo.get_plan_version(session, run.id, version - 1) if version > 1 else None
            return PlanningInput(
                configuration=ProjectConfiguration.model_validate(project.configuration),
                notes=notes,
                previous_plan=previous.content if previous else None,
                revision_comment=job.payload.get("revision_comment"),
            )

    def _commit(self, job: JobSnapshot, owner: str, version: int, result, attempt_ids: dict[int, uuid.UUID]) -> str:
        now = self._clock()
        with transaction(self._factory) as session:
            run = repo.get_run(session, job.run_id, lock=True)
            if not repo.finish_job_if_owner(session, job.id, owner, JobStatus.DONE, now):
                raise _LostLease
            if run is None or run.state != RunState.PLANNING:
                return "discarded"  # cancelled while the model was running
            if result.plan is None:
                run.failure_code = result.failure_code
                run.failure_message = (result.failure_message or "")[:500]
                transition(session, run, RunState.FAILED, now, {"failure_code": result.failure_code})
                append_audit(
                    session,
                    actor_type="worker",
                    actor_id=owner,
                    action="plan.failed",
                    entity_type="run",
                    entity_id=str(run.id),
                    data={"failure_code": result.failure_code},
                )
                return "failed"
            if repo.get_plan_version(session, run.id, version) is not None:
                return "duplicate"
            succeeded = next(record for record in result.attempts if record.outcome == "succeeded")
            plan = result.plan
            repo.add_plan_version(
                session,
                run_id=run.id,
                version=version,
                content=plan.model_dump(mode="json"),
                attempt_id=attempt_ids[succeeded.attempt],
                created_at=now,
            )
            repo.add_tasks(
                session,
                [
                    EngineeringTask(
                        run_id=run.id,
                        plan_version=version,
                        position=index,
                        key=task.key,
                        title=task.title,
                        description=task.description,
                        acceptance_criteria=task.acceptance_criteria,
                        depends_on=task.depends_on,
                        requirement_ids=task.requirement_ids,
                        suggested_agent=task.suggested_agent,
                    )
                    for index, task in enumerate(plan.tasks)
                ],
            )
            repo.close_pending_approvals(session, run.id, ApprovalStatus.SUPERSEDED, now)
            approval = repo.add_approval(
                session,
                run_id=run.id,
                plan_version=version,
                gate="plan",
                status=ApprovalStatus.PENDING.value,
                created_at=now,
            )
            run.current_plan_version = version
            repo.append_event(
                session,
                run,
                RunEventType.PLAN_CREATED,
                {
                    "plan_version": version,
                    "task_count": len(plan.tasks),
                    "open_question_count": len(plan.open_questions),
                },
                now,
            )
            repo.append_event(
                session,
                run,
                RunEventType.APPROVAL_REQUESTED,
                {"approval_id": str(approval.id), "plan_version": version, "gate": "plan"},
                now,
            )
            transition(session, run, RunState.AWAITING_APPROVAL, now, {"plan_version": version})
            append_audit(
                session,
                actor_type="worker",
                actor_id=owner,
                action="plan.created",
                entity_type="run",
                entity_id=str(run.id),
                data={"plan_version": version},
            )
            return "planned"
