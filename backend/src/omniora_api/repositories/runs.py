from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from ..db.models import AgentAttempt, Approval, EngineeringTask, Job, PlanVersion, Project, Run, RunEvent
from ..domain.runs import ACTIVE_STATES, ApprovalStatus, JobStatus, RunState


def get_run_for_owner(session: Session, run_id: uuid.UUID, owner_id: uuid.UUID, *, lock: bool = False) -> Run | None:
    query = (
        select(Run).join(Project, Project.id == Run.project_id).where(Run.id == run_id, Project.owner_id == owner_id)
    )
    if lock:
        query = query.with_for_update(of=Run)
    return session.scalar(query)


def get_run(session: Session, run_id: uuid.UUID, *, lock: bool = False) -> Run | None:
    query = select(Run).where(Run.id == run_id)
    if lock:
        query = query.with_for_update()
    return session.scalar(query)


def get_run_by_idempotency_key(session: Session, project_id: uuid.UUID, key: str) -> Run | None:
    return session.scalar(select(Run).where(Run.project_id == project_id, Run.idempotency_key == key))


def list_project_runs(session: Session, project_id: uuid.UUID, agent_role: str, limit: int = 50) -> list[Run]:
    return list(
        session.scalars(
            select(Run)
            .where(Run.project_id == project_id, Run.agent_role == agent_role)
            .order_by(Run.created_at.desc(), Run.id.desc())
            .limit(limit)
        )
    )


def count_runs_created_since(session: Session, user_id: uuid.UUID, since: datetime) -> int:
    return session.scalar(select(func.count()).where(Run.created_by == user_id, Run.created_at >= since)) or 0


def append_event(session: Session, run: Run, event_type: str, data: dict[str, Any], now: datetime) -> RunEvent:
    """The caller must hold the run row lock (`lock=True`) so sequence numbers are gap-free and
    committed in order; SSE replay relies on that."""
    run.event_seq += 1
    event = RunEvent(run_id=run.id, seq=run.event_seq, type=event_type, data=data, at=now)
    session.add(event)
    session.flush()
    return event


def list_events(session: Session, run_id: uuid.UUID, after_seq: int, limit: int = 200) -> list[RunEvent]:
    return list(
        session.scalars(
            select(RunEvent)
            .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
            .order_by(RunEvent.seq)
            .limit(limit)
        )
    )


def add_job(
    session: Session,
    *,
    run_id: uuid.UUID,
    kind: str,
    payload: dict[str, Any],
    dedupe_key: str,
    max_deliveries: int,
    now: datetime,
) -> Job:
    job = Job(
        run_id=run_id,
        kind=kind,
        payload=payload,
        status=JobStatus.QUEUED,
        max_deliveries=max_deliveries,
        available_at=now,
        dedupe_key=dedupe_key,
        created_at=now,
    )
    session.add(job)
    session.flush()
    return job


def claim_next_job(session: Session, *, owner: str, now: datetime, lease_seconds: int) -> Job | None:
    """Claims one queued job, or a leased job whose lease expired (its worker died). Concurrent
    workers skip rows another transaction has locked, so a job is claimed by one worker at a time."""
    job = session.scalar(
        select(Job)
        .where(
            or_(
                and_(Job.status == JobStatus.QUEUED, Job.available_at <= now),
                and_(Job.status == JobStatus.LEASED, Job.lease_expires_at < now),
            )
        )
        .order_by(Job.available_at, Job.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    job.status = JobStatus.LEASED
    job.lease_owner = owner
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.deliveries += 1
    session.flush()
    return job


def renew_lease(session: Session, job_id: uuid.UUID, owner: str, now: datetime, lease_seconds: int) -> bool:
    result = session.execute(
        update(Job)
        .where(Job.id == job_id, Job.lease_owner == owner, Job.status == JobStatus.LEASED, Job.lease_expires_at >= now)
        .values(lease_expires_at=now + timedelta(seconds=lease_seconds))
    )
    return result.rowcount == 1


def finish_job_if_owner(session: Session, job_id: uuid.UUID, owner: str, status: JobStatus, now: datetime) -> bool:
    """Marks the job finished only if this worker still holds a valid lease. A worker whose lease
    expired (and may have been re-delivered) gets False and must roll back its results."""
    result = session.execute(
        update(Job)
        .where(Job.id == job_id, Job.lease_owner == owner, Job.status == JobStatus.LEASED, Job.lease_expires_at >= now)
        .values(status=status, lease_expires_at=None)
    )
    return result.rowcount == 1


def release_job_for_retry(session: Session, job_id: uuid.UUID, owner: str, available_at: datetime, error: str) -> bool:
    result = session.execute(
        update(Job)
        .where(Job.id == job_id, Job.lease_owner == owner, Job.status == JobStatus.LEASED)
        .values(
            status=JobStatus.QUEUED,
            lease_owner=None,
            lease_expires_at=None,
            available_at=available_at,
            last_error=error[:500],
        )
    )
    return result.rowcount == 1


def cancel_open_jobs(session: Session, run_id: uuid.UUID) -> None:
    session.execute(
        update(Job)
        .where(Job.run_id == run_id, Job.status.in_([JobStatus.QUEUED, JobStatus.LEASED]))
        .values(status=JobStatus.CANCELLED, lease_expires_at=None)
    )


def add_attempt(session: Session, **values: Any) -> AgentAttempt:
    attempt = AgentAttempt(**values)
    session.add(attempt)
    session.flush()
    return attempt


def list_attempts(session: Session, run_id: uuid.UUID) -> list[AgentAttempt]:
    return list(
        session.scalars(
            select(AgentAttempt).where(AgentAttempt.run_id == run_id).order_by(AgentAttempt.created_at, AgentAttempt.id)
        )
    )


def add_plan_version(session: Session, **values: Any) -> PlanVersion:
    plan = PlanVersion(**values)
    session.add(plan)
    session.flush()
    return plan


def get_plan_version(session: Session, run_id: uuid.UUID, version: int) -> PlanVersion | None:
    return session.scalar(select(PlanVersion).where(PlanVersion.run_id == run_id, PlanVersion.version == version))


def add_tasks(session: Session, tasks: list[EngineeringTask]) -> None:
    session.add_all(tasks)
    session.flush()


def list_tasks(session: Session, run_id: uuid.UUID, plan_version: int) -> list[EngineeringTask]:
    return list(
        session.scalars(
            select(EngineeringTask)
            .where(EngineeringTask.run_id == run_id, EngineeringTask.plan_version == plan_version)
            .order_by(EngineeringTask.position)
        )
    )


def add_approval(session: Session, **values: Any) -> Approval:
    approval = Approval(**values)
    session.add(approval)
    session.flush()
    return approval


def get_approval(session: Session, run_id: uuid.UUID, approval_id: uuid.UUID, *, lock: bool = False) -> Approval | None:
    query = select(Approval).where(Approval.id == approval_id, Approval.run_id == run_id)
    if lock:
        query = query.with_for_update()
    return session.scalar(query)


def list_approvals(session: Session, run_id: uuid.UUID) -> list[Approval]:
    return list(
        session.scalars(select(Approval).where(Approval.run_id == run_id).order_by(Approval.created_at, Approval.id))
    )


def close_pending_approvals(session: Session, run_id: uuid.UUID, status: ApprovalStatus, now: datetime) -> None:
    session.execute(
        update(Approval)
        .where(Approval.run_id == run_id, Approval.status == ApprovalStatus.PENDING)
        .values(status=status, decided_at=now)
    )


def is_active(run: Run) -> bool:
    return RunState(run.state) in ACTIVE_STATES
