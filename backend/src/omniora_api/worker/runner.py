"""Claim loop. Start with `python -m omniora_api.worker`; run as many processes as needed.

Delivery semantics: at-least-once. A job is leased to one worker at a time (row locks with
SKIP LOCKED); the lease is renewed in the background while the job runs. If the process dies, the
lease expires and another worker re-delivers the job. After `max_deliveries` deliveries the job
and its run fail with `worker-exhausted` instead of looping forever. Model calls may therefore
repeat after a crash, but results only commit under a valid lease (see planning.py).

Jobs are dispatched by kind: `plan` (Project Manager) and `requirements-turn` (Requirements
Analyst). An exhausted planning job fails its run; an exhausted discovery job fails only its turn,
which keeps the user's answers and can be retried.
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import uuid
from datetime import timedelta

from ..audit import append_audit
from ..db.models import Job
from ..db.session import SessionFactory, transaction
from ..domain.runs import JobStatus, RunState
from ..repositories import runs as repo
from ..services import Clock, utcnow
from ..services.requirements import DISCOVERY_JOB
from ..services.runs import transition
from .discovery import DiscoveryJobHandler, fail_turn
from .planning import JobSnapshot, LeaseState, PlanningJobHandler

logger = logging.getLogger("omniora.worker")


def default_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"


class LeaseKeeper(threading.Thread):
    """Renews the lease every third of its duration; marks it lost if renewal fails."""

    def __init__(
        self,
        factory: SessionFactory,
        job_id: uuid.UUID,
        owner: str,
        lease_seconds: int,
        lease: LeaseState,
        clock: Clock,
    ) -> None:
        super().__init__(daemon=True, name=f"lease-{job_id}")
        self._factory, self._job_id, self._owner = factory, job_id, owner
        self._lease_seconds, self._lease, self._clock = lease_seconds, lease, clock
        self._stop_requested = threading.Event()  # not `_stop`: Thread uses that name internally

    def run(self) -> None:
        while not self._stop_requested.wait(self._lease_seconds / 3):
            try:
                with transaction(self._factory) as session:
                    renewed = repo.renew_lease(session, self._job_id, self._owner, self._clock(), self._lease_seconds)
            except Exception:
                logger.exception("lease renewal failed", extra={"job_id": str(self._job_id)})
                renewed = False
            if not renewed:
                self._lease.mark_lost()
                return

    def stop(self) -> None:
        self._stop_requested.set()


class Worker:
    def __init__(
        self,
        factory: SessionFactory,
        planning: PlanningJobHandler,
        *,
        discovery: DiscoveryJobHandler | None = None,
        owner: str | None = None,
        lease_seconds: int = 60,
        poll_seconds: float = 1.0,
        clock: Clock = utcnow,
    ) -> None:
        self._factory = factory
        self._planning = planning
        self._discovery = discovery
        self.owner = owner or default_worker_id()
        self._lease_seconds = lease_seconds
        self._poll_seconds = poll_seconds
        self._clock = clock

    def claim(self) -> JobSnapshot | None:
        """Claims one job, failing it instead if it has exhausted its deliveries."""
        now = self._clock()
        with transaction(self._factory) as session:
            job = repo.claim_next_job(session, owner=self.owner, now=now, lease_seconds=self._lease_seconds)
            if job is None:
                return None
            if job.deliveries > job.max_deliveries:
                job.status = JobStatus.FAILED
                job.last_error = "Delivery limit reached; the worker repeatedly stopped before finishing."
                if job.kind == DISCOVERY_JOB:
                    message = "The analyst turn was interrupted too many times. Retry it; your answers are kept."
                    fail_turn(
                        session, job.run_id, int(job.payload["turn"]), "worker-exhausted", message, self.owner, now
                    )
                else:
                    self._fail_run(
                        session,
                        job.run_id,
                        "worker-exhausted",
                        "Planning was interrupted too many times. Start a new run.",
                    )
                return None
            return JobSnapshot(
                id=job.id, run_id=job.run_id, payload=dict(job.payload), deliveries=job.deliveries, kind=job.kind
            )

    def _fail_run(self, session, run_id: uuid.UUID, code: str, message: str) -> None:
        run = repo.get_run(session, run_id, lock=True)
        if run is None or run.state not in (RunState.QUEUED, RunState.PLANNING):
            return
        run.failure_code, run.failure_message = code, message
        transition(session, run, RunState.FAILED, self._clock(), {"failure_code": code})
        append_audit(
            session,
            actor_type="worker",
            actor_id=self.owner,
            action="run.failed",
            entity_type="run",
            entity_id=str(run.id),
            data={"failure_code": code},
        )

    def process(self, job: JobSnapshot) -> str:
        lease = LeaseState()
        keeper = LeaseKeeper(self._factory, job.id, self.owner, self._lease_seconds, lease, self._clock)
        keeper.start()
        try:
            if job.kind == DISCOVERY_JOB:
                if self._discovery is None:
                    raise RuntimeError("This worker has no requirements-turn handler")
                return self._discovery.handle(job, self.owner, lease)
            return self._planning.handle(job, self.owner, lease)
        except Exception as exc:
            logger.exception("job failed unexpectedly", extra={"job_id": str(job.id)})
            self._handle_crash(job, exc)
            return "error"
        finally:
            keeper.stop()

    def _handle_crash(self, job: JobSnapshot, exc: Exception) -> None:
        with transaction(self._factory) as session:
            current = session.get(Job, job.id)
            if current is None or current.lease_owner != self.owner or current.status != JobStatus.LEASED:
                return
            if job.deliveries >= current.max_deliveries:
                current.status = JobStatus.FAILED
                current.last_error = type(exc).__name__
                if job.kind == DISCOVERY_JOB:
                    message = "The analyst turn failed because of an internal error. Retry it; your answers are kept."
                    fail_turn(
                        session,
                        job.run_id,
                        int(job.payload["turn"]),
                        "worker-error",
                        message,
                        self.owner,
                        self._clock(),
                    )
                else:
                    self._fail_run(session, job.run_id, "worker-error", "Planning failed because of an internal error.")
            else:
                backoff = timedelta(seconds=min(2**job.deliveries, 60))
                repo.release_job_for_retry(session, job.id, self.owner, self._clock() + backoff, type(exc).__name__)

    def run_once(self) -> bool:
        job = self.claim()
        if job is None:
            return False
        outcome = self.process(job)
        logger.info("job processed", extra={"job_id": str(job.id), "outcome": outcome, "delivery": job.deliveries})
        return True

    def run_forever(self, stop: threading.Event) -> None:
        logger.info("worker started", extra={"worker": self.owner})
        while not stop.is_set():
            try:
                worked = self.run_once()
            except Exception:
                logger.exception("worker loop error")
                worked = False
            if not worked:
                stop.wait(self._poll_seconds)
        logger.info("worker stopped", extra={"worker": self.owner})
