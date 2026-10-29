"""Handler for `requirements-turn` jobs: runs one Requirements Analyst turn and commits it.

Same commit protocol as planning.py:
1. Start: lock the run, move it to `discovering`, and mark the turn `running`.
2. Model attempts run outside any transaction; each finished attempt is persisted immediately.
3. Commit: lock the run and mark the job done only while this worker still holds a valid lease.
   Otherwise everything rolls back. Unique (run, version) and (run, question key) constraints
   are a second guard against a duplicate delivery committing twice.
A failed turn never fails the session: the turn is marked failed, every answer is kept, and the
user can retry it.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from ..agents.project_manager import AttemptRecord
from ..agents.requirements_analyst import DiscoveryInput, DiscoveryResult, run_requirements_analyst
from ..audit import append_audit
from ..config import Settings
from ..db.models import DiscoveryQuestion, Project
from ..db.session import SessionFactory, transaction
from ..domain.projects import ProjectConfiguration
from ..domain.requirements import RequirementsDocument, content_sha256
from ..domain.runs import JobStatus, RunEventType, RunState, TurnStatus
from ..llm.base import ModelProvider
from ..repositories import projects as projects_repo
from ..repositories import requirements as req_repo
from ..repositories import runs as repo
from ..services import Clock, utcnow
from ..services.requirements import question_states
from ..services.runs import transition
from .planning import JobSnapshot, LeaseState, _LostLease

logger = logging.getLogger("omniora.worker.discovery")


@dataclass(frozen=True)
class _Prepared:
    discovery: DiscoveryInput
    parent_version_id: uuid.UUID | None


def fail_turn(session, run_id: uuid.UUID, number: int, code: str, message: str, owner: str, now) -> None:
    """Marks a turn failed (keeping every answer). Caller holds no run lock; this takes it."""
    run = repo.get_run(session, run_id, lock=True)
    turn = req_repo.get_turn(session, run_id, number, lock=True)
    if run is None or turn is None or turn.status not in (TurnStatus.QUEUED, TurnStatus.RUNNING):
        return
    turn.status = TurnStatus.FAILED.value
    turn.failure_code, turn.failure_message = code, message[:500]
    turn.completed_at = now
    repo.append_event(session, run, RunEventType.TURN_FAILED, {"turn": number, "failure_code": code}, now)
    append_audit(
        session,
        actor_type="worker",
        actor_id=owner,
        action="requirements.turn-failed",
        entity_type="run",
        entity_id=str(run.id),
        data={"turn": number, "failure_code": code},
    )


class DiscoveryJobHandler:
    def __init__(
        self, factory: SessionFactory, provider: ModelProvider, settings: Settings, clock: Clock = utcnow
    ) -> None:
        self._factory = factory
        self._provider = provider
        self._settings = settings
        self._clock = clock

    def handle(self, job: JobSnapshot, owner: str, lease: LeaseState) -> str:
        number = int(job.payload["turn"])
        prepared = self._start(job, owner, number)
        if prepared is None:
            return "skipped"
        attempt_ids: dict[int, uuid.UUID] = {}

        def before_attempt(attempt: int) -> bool:
            if lease.lost:
                return False
            now = self._clock()
            with transaction(self._factory) as session:
                run = repo.get_run(session, job.run_id, lock=True)
                turn = req_repo.get_turn(session, job.run_id, number)
                if (
                    run is None
                    or run.state != RunState.DISCOVERING
                    or turn is None
                    or turn.status != TurnStatus.RUNNING
                ):
                    return False
                repo.append_event(session, run, RunEventType.ATTEMPT_STARTED, {"attempt": attempt, "turn": number}, now)
            return True

        def on_attempt(record: AttemptRecord) -> None:
            now = self._clock()
            with transaction(self._factory) as session:
                attempt = repo.add_attempt(
                    session,
                    run_id=job.run_id,
                    job_id=job.id,
                    plan_version=number,
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
                            "turn": number,
                            "outcome": record.outcome,
                            "error_code": record.error_code,
                            "problem_count": len(record.validation_errors),
                        },
                        now,
                    )

        result = run_requirements_analyst(
            self._provider,
            prepared.discovery,
            max_attempts=self._settings.analyst_max_attempts,
            max_output_tokens=self._settings.analyst_output_tokens,
            request_token_budget=self._settings.analyst_token_budget,
            effort=self._settings.planning_effort,
            timeout_seconds=self._settings.model_timeout_seconds,
            before_attempt=before_attempt,
            on_attempt=on_attempt,
        )
        try:
            return self._commit(job, owner, number, prepared, result, attempt_ids)
        except _LostLease:
            logger.warning("discovery result discarded: lease lost", extra={"job_id": str(job.id)})
            return "lost-lease"

    def _start(self, job: JobSnapshot, owner: str, number: int) -> _Prepared | None:
        now = self._clock()
        with transaction(self._factory) as session:
            run = repo.get_run(session, job.run_id, lock=True)
            turn = req_repo.get_turn(session, job.run_id, number, lock=True)
            startable = run is not None and run.state in (RunState.QUEUED, RunState.DISCOVERING, RunState.NEEDS_CHANGES)
            if not startable or turn is None or turn.status not in (TurnStatus.QUEUED, TurnStatus.RUNNING):
                repo.finish_job_if_owner(session, job.id, owner, JobStatus.CANCELLED, now)
                return None
            if run.state != RunState.DISCOVERING:
                transition(session, run, RunState.DISCOVERING, now, {"turn": number})
            turn.status = TurnStatus.RUNNING.value
            project = session.get(Project, run.project_id)
            if project is None:
                return None
            latest = req_repo.latest_version(session, run.id)
            # A new session starts from the project's last approved version, so ids stay stable across sessions.
            base = latest or req_repo.latest_approved_for_project(session, project.id)
            answers = req_repo.latest_answers(session, run.id)
            questions = req_repo.list_questions(session, run.id)
            values = {
                q.key: answers[q.id].value.get("value")
                for q in questions
                if q.id in answers and not answers[q.id].unknown
            }
            final = turn.trigger in ("answers", "more-questions") and number >= self._settings.analyst_max_turns
            discovery = DiscoveryInput(
                configuration=ProjectConfiguration.model_validate(project.configuration),
                notes=[note.content for note in projects_repo.list_notes(session, project.id)],
                previous=RequirementsDocument.model_validate(base.content) if base else None,
                questions=question_states(session, run.id),
                answers=values,
                turn=number,
                max_turns=self._settings.analyst_max_turns,
                final_turn=final,
                first_question_number=len(questions) + 1,
                revision_comment=turn.revision_comment,
            )
            return _Prepared(discovery, base.id if base else None)

    def _commit(
        self,
        job: JobSnapshot,
        owner: str,
        number: int,
        prepared: _Prepared,
        result: DiscoveryResult,
        attempt_ids: dict[int, uuid.UUID],
    ) -> str:
        now = self._clock()
        with transaction(self._factory) as session:
            run = repo.get_run(session, job.run_id, lock=True)
            if not repo.finish_job_if_owner(session, job.id, owner, JobStatus.DONE, now):
                raise _LostLease
            turn = req_repo.get_turn(session, job.run_id, number, lock=True)
            if run is None or run.state != RunState.DISCOVERING or turn is None or turn.status != TurnStatus.RUNNING:
                return "discarded"  # cancelled, or another delivery already finished this turn
            if result.turn is None or result.turn.document is None:
                fail_turn(
                    session,
                    run.id,
                    number,
                    result.failure_code or "invalid-output",
                    result.failure_message or "The analyst turn failed.",
                    owner,
                    now,
                )
                return "turn-failed"

            document = result.turn.document
            latest = req_repo.latest_version(session, run.id)
            version = (latest.version if latest else 0) + 1
            existing = {q.key: q for q in req_repo.list_questions(session, run.id)}
            new_questions = []
            for state in result.turn.questions:
                if state.key in existing:
                    if state.status == "withdrawn" and existing[state.key].status == "open":
                        existing[state.key].status = "withdrawn"
                    continue
                proposed = result.output.questions[len(new_questions)] if result.output else None
                new_questions.append(
                    DiscoveryQuestion(
                        run_id=run.id,
                        turn_number=number,
                        key=state.key,
                        prompt=state.prompt,
                        why=proposed.why if proposed else "",
                        kind=state.kind,
                        options=list(state.options),
                        blocking=state.blocking,
                        topic=state.topic,
                        relates_to=list(proposed.relates_to) if proposed else [],
                        status="open",
                        created_at=now,
                    )
                )
            req_repo.add_questions(session, new_questions)
            succeeded = next(record for record in result.attempts if record.outcome == "succeeded")
            sha = content_sha256(document)
            req_repo.add_version(
                session,
                run_id=run.id,
                project_id=run.project_id,
                version=version,
                parent_version_id=prepared.parent_version_id,
                schema_version=document.schema_version,
                content=document.model_dump(mode="json"),
                content_sha256=sha,
                turn_number=number,
                attempt_id=attempt_ids[succeeded.attempt],
                created_at=now,
            )
            turn.status = TurnStatus.COMPLETED.value
            turn.requirements_version = version
            turn.completed_at = now
            repo.append_event(
                session,
                run,
                RunEventType.REQUIREMENTS_VERSION_CREATED,
                {
                    "version": version,
                    "requirement_count": len(document.active()),
                    "question_count": len(new_questions),
                    "ready": document.readiness.ready,
                },
                now,
            )
            repo.append_event(session, run, RunEventType.TURN_COMPLETED, {"turn": number, "version": version}, now)
            if document.readiness.ready:
                transition(session, run, RunState.READY_FOR_REVIEW, now, {"version": version})
            append_audit(
                session,
                actor_type="worker",
                actor_id=owner,
                action="requirements.version-created",
                entity_type="run",
                entity_id=str(run.id),
                data={"version": version, "content_sha256": sha, "turn": number},
            )
            return "completed"
