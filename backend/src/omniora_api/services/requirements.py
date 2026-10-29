"""Requirements Analyst (Agent 2) use cases: discovery sessions, answers, turns, versions, approval.

A session is a run with agent_role "requirements-analyst", so it shares the run row lock, event
sequence, jobs and leases, approvals, and the audit chain with planning runs. Rules:
- Every state change happens under the run's row lock and appends its event in the same transaction.
- At most one turn is in flight per session (partial unique index), so concurrent answer
  submissions cannot advance the same turn twice; the second gets `conflict`.
- Answers are append-only and survive any worker crash: a failed turn keeps them and can be retried.
- A submitted version is frozen before approval; an approved version is immutable (database trigger).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError

from ..audit import append_audit
from ..db.models import (
    AgentAttempt,
    Approval,
    DiscoveryAnswer,
    DiscoveryQuestion,
    DiscoveryTurn,
    RequirementsVersion,
    Run,
)
from ..db.session import SessionFactory, transaction
from ..domain.requirements import (
    DocumentDiff,
    QuestionState,
    RequirementsDocument,
    diff_documents,
    readiness_blockers,
)
from ..domain.runs import (
    TERMINAL_STATES,
    AgentRole,
    ApprovalStatus,
    RequirementsDecision,
    RunEventType,
    RunState,
    TurnStatus,
)
from ..errors import ApiError
from ..repositories import projects as projects_repo
from ..repositories import requirements as req_repo
from ..repositories import runs as repo
from . import Clock, utcnow
from .projects import parse_project_id
from .runs import transition

DISCOVERY_JOB = "requirements-turn"
AGENT_ROLE = AgentRole.REQUIREMENTS_ANALYST.value
REQUIREMENTS_GATE = "requirements"
FREE_TEXT_MAX = 2000


def turn_job_key(run_id: uuid.UUID, number: int, tries: int) -> str:
    return f"{DISCOVERY_JOB}:{run_id}:t{number}:r{tries}"


@dataclass(frozen=True)
class AnswerInput:
    question_key: str
    value: Any = None
    unknown: bool = False


@dataclass(frozen=True)
class QuestionView:
    question: DiscoveryQuestion
    answer: DiscoveryAnswer | None


@dataclass(frozen=True)
class SessionDetail:
    run: Run
    turn: DiscoveryTurn | None
    questions: list[QuestionView]
    version: RequirementsVersion | None
    approvals: list[Approval]
    attempts: list[AgentAttempt]
    max_turns: int


def question_states(session, run_id: uuid.UUID) -> tuple[QuestionState, ...]:
    """Persisted questions with their current answers, in the form the domain validator uses."""
    answers = req_repo.latest_answers(session, run_id)
    states = []
    for question in req_repo.list_questions(session, run_id):
        answer = answers.get(question.id)
        states.append(
            QuestionState(
                key=question.key,
                prompt=question.prompt,
                kind=question.kind,  # type: ignore[arg-type]
                options=tuple(question.options),
                blocking=question.blocking,
                topic=question.topic,  # type: ignore[arg-type]
                status=question.status,  # type: ignore[arg-type]
                unknown=bool(answer and answer.unknown),
            )
        )
    return tuple(states)


def _validated_value(question: DiscoveryQuestion, answer: AnswerInput) -> Any:
    """The stored value for a known answer, or raises `validation` with a user-safe message."""
    key, value = question.key, answer.value
    if answer.unknown:
        if value is not None:
            raise ApiError("validation", f'{key}: an "I don\'t know" answer has no value.')
        return None
    if question.kind == "single-choice":
        if not isinstance(value, str) or value not in question.options:
            raise ApiError("validation", f"{key}: choose one of the offered options.")
        return value
    if question.kind == "multiple-choice":
        if (
            not isinstance(value, list)
            or not value
            or len(set(value)) != len(value)
            or any(not isinstance(item, str) or item not in question.options for item in value)
        ):
            raise ApiError("validation", f"{key}: choose one or more of the offered options.")
        return value
    if question.kind == "yes-no":
        if not isinstance(value, bool):
            raise ApiError("validation", f"{key}: answer yes or no.")
        return value
    if not isinstance(value, str) or not value.strip() or len(value) > FREE_TEXT_MAX:
        raise ApiError("validation", f"{key}: write an answer of 1 to {FREE_TEXT_MAX} characters.")
    return value.strip()


class RequirementsService:
    def __init__(
        self,
        factory: SessionFactory,
        *,
        runs_per_user_per_hour: int,
        turns_per_user_per_hour: int,
        max_turns: int,
        job_max_deliveries: int,
        provider_configured: bool,
        clock: Clock = utcnow,
    ) -> None:
        self._factory = factory
        self._runs_limit = runs_per_user_per_hour
        self._turns_limit = turns_per_user_per_hour
        self._max_turns = max_turns
        self._max_deliveries = job_max_deliveries
        self._provider_configured = provider_configured
        self._clock = clock

    # --- helpers --------------------------------------------------------------------------

    def _require(self, session, user_id: uuid.UUID, session_id: uuid.UUID, *, lock: bool = False) -> Run:
        run = repo.get_run_for_owner(session, session_id, user_id, lock=lock)
        if run is None or run.agent_role != AGENT_ROLE:
            raise ApiError("not-found", "This requirements session does not exist.")
        return run

    def _require_provider(self) -> None:
        if not self._provider_configured:
            raise ApiError(
                "provider-not-configured",
                "Requirements discovery is unavailable: no model provider is configured on the server. "
                "An operator must set the selected provider's key (ANTHROPIC_API_KEY or GROQ_API_KEY) "
                "for the backend and worker.",
            )

    def _queue_turn(
        self, session, run: Run, user_id: uuid.UUID, number: int, trigger: str, now, comment: str | None = None
    ) -> DiscoveryTurn:
        if trigger in ("answers", "more-questions") and number > self._max_turns:
            raise ApiError(
                "conflict",
                f"This session has used all {self._max_turns} discovery turns. Submit the current version for "
                "review, or start a new session.",
            )
        since = now - timedelta(hours=1)
        if req_repo.count_turns_created_since(session, user_id, since) >= self._turns_limit:
            raise ApiError(
                "rate-limited",
                "You have requested too many analyst turns in the last hour. Try again later.",
                headers={"Retry-After": "3600"},
            )
        turn = req_repo.add_turn(
            session,
            run_id=run.id,
            number=number,
            status=TurnStatus.QUEUED.value,
            trigger=trigger,
            revision_comment=comment,
            created_by=user_id,
            created_at=now,
        )
        repo.add_job(
            session,
            run_id=run.id,
            kind=DISCOVERY_JOB,
            payload={"turn": number, "tries": 1},
            dedupe_key=turn_job_key(run.id, number, 1),
            max_deliveries=self._max_deliveries,
            now=now,
        )
        repo.append_event(session, run, RunEventType.TURN_QUEUED, {"turn": number, "trigger": trigger}, now)
        return turn

    def _detail(self, session, run: Run) -> SessionDetail:
        answers = req_repo.latest_answers(session, run.id)
        return SessionDetail(
            run=run,
            turn=req_repo.latest_turn(session, run.id),
            questions=[QuestionView(q, answers.get(q.id)) for q in req_repo.list_questions(session, run.id)],
            version=req_repo.latest_version(session, run.id),
            approvals=repo.list_approvals(session, run.id),
            attempts=repo.list_attempts(session, run.id),
            max_turns=self._max_turns,
        )

    def _audit(self, session, user_id: uuid.UUID, action: str, run: Run, data: dict[str, Any] | None = None) -> None:
        append_audit(
            session,
            actor_type="user",
            actor_id=str(user_id),
            action=action,
            entity_type="run",
            entity_id=str(run.id),
            data=data,
        )

    # --- commands -------------------------------------------------------------------------

    def start(self, user_id: uuid.UUID, project_id: str, idempotency_key: str) -> tuple[Run, bool]:
        """Returns (session, created). Repeating a key returns the original session."""
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
            self._require_provider()
            now = self._clock()
            if repo.count_runs_created_since(session, user_id, now - timedelta(hours=1)) >= self._runs_limit:
                raise ApiError(
                    "rate-limited",
                    "You have started too many runs in the last hour. Try again later.",
                    headers={"Retry-After": "3600"},
                )
            run = Run(
                project_id=project.id,
                created_by=user_id,
                agent_role=AGENT_ROLE,
                state=RunState.QUEUED.value,
                idempotency_key=idempotency_key,
                created_at=now,
                updated_at=now,
            )
            session.add(run)
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                raise ApiError(
                    "conflict", "Another run (planning or requirements discovery) is in progress for this project."
                ) from None
            repo.append_event(session, run, RunEventType.RUN_CREATED, {"agent": AGENT_ROLE}, now)
            self._queue_turn(session, run, user_id, 1, "start", now)
            self._audit(session, user_id, "requirements.session-started", run, {"project_id": str(project.id)})
            return run, True

    def list_for_project(self, user_id: uuid.UUID, project_id: str) -> list[Run]:
        try:
            pid = parse_project_id(project_id)
        except ApiError as error:
            if error.code == "read-only":
                return []
            raise
        with transaction(self._factory) as session:
            if projects_repo.get_owned_project(session, pid, user_id) is None:
                raise ApiError("not-found", "This project no longer exists.")
            return repo.list_project_runs(session, pid, AGENT_ROLE)

    def detail(self, user_id: uuid.UUID, session_id: uuid.UUID) -> SessionDetail:
        with transaction(self._factory) as session:
            return self._detail(session, self._require(session, user_id, session_id))

    def answer(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        idempotency_key: str,
        answers: list[AnswerInput],
        *,
        advance: bool,
    ) -> SessionDetail:
        if not answers and not advance:
            raise ApiError("validation", "Provide at least one answer, or ask the analyst to continue.")
        keys = [a.question_key for a in answers]
        if len(set(keys)) != len(keys):
            raise ApiError("validation", "Each question can be answered once per submission.")
        now = self._clock()
        with transaction(self._factory) as session:
            run = self._require(session, user_id, session_id, lock=True)
            if req_repo.submission_exists(session, run.id, idempotency_key):
                return self._detail(session, run)  # a retried request: already applied
            state = RunState(run.state)
            if state not in (RunState.DISCOVERING, RunState.READY_FOR_REVIEW):
                raise ApiError(
                    "conflict", f"This session is {state.value.replace('-', ' ')}; answers cannot change now."
                )
            latest = req_repo.latest_turn(session, run.id)
            if latest is not None and latest.status in (TurnStatus.QUEUED, TurnStatus.RUNNING):
                raise ApiError("conflict", "The analyst is still working on the previous turn. Wait for it to finish.")
            # Changing anything after readiness re-opens discovery, so a stale version is never submitted.
            advance = advance or (state == RunState.READY_FOR_REVIEW and bool(answers))
            if advance and latest is not None and latest.status == TurnStatus.FAILED:
                raise ApiError("conflict", "The last analyst turn failed. Retry it; your answers are kept.")

            by_key = {q.key: q for q in req_repo.list_questions(session, run.id)}
            rows = []
            for answer in answers:
                question = by_key.get(answer.question_key)
                if question is None:
                    raise ApiError("not-found", f"Question {answer.question_key} does not exist in this session.")
                if question.status == "withdrawn":
                    raise ApiError("conflict", f"Question {question.key} was withdrawn by the analyst.")
                value = _validated_value(question, answer)
                rows.append(
                    DiscoveryAnswer(
                        run_id=run.id,
                        question_id=question.id,
                        value={"value": value},
                        unknown=answer.unknown,
                        answered_by=user_id,
                        idempotency_key=idempotency_key,
                        created_at=now,
                    )
                )
                question.status = "answered"
            if rows:
                req_repo.add_answers(session, rows)
                unknown = sum(1 for a in answers if a.unknown)
                repo.append_event(
                    session, run, RunEventType.ANSWERS_SUBMITTED, {"count": len(rows), "unknown_count": unknown}, now
                )
                self._audit(
                    session, user_id, "requirements.answers-submitted", run, {"question_keys": keys, "unknown": unknown}
                )
            if advance:
                if state == RunState.READY_FOR_REVIEW:
                    transition(session, run, RunState.DISCOVERING, now, {"reason": "answers-changed"})
                number = (latest.number if latest else 0) + 1
                self._queue_turn(session, run, user_id, number, "answers" if rows else "more-questions", now)
            return self._detail(session, run)

    def retry_turn(self, user_id: uuid.UUID, session_id: uuid.UUID) -> SessionDetail:
        now = self._clock()
        with transaction(self._factory) as session:
            run = self._require(session, user_id, session_id, lock=True)
            if RunState(run.state) in TERMINAL_STATES:
                raise ApiError("conflict", f"This session already finished ({run.state}).")
            turn = req_repo.latest_turn(session, run.id)
            if turn is None or turn.status in (TurnStatus.QUEUED, TurnStatus.RUNNING):
                return self._detail(session, run)  # already queued or running: idempotent
            if turn.status != TurnStatus.FAILED:
                raise ApiError("conflict", "The latest analyst turn did not fail, so there is nothing to retry.")
            self._require_provider()
            turn.tries += 1
            turn.status = TurnStatus.QUEUED.value
            turn.failure_code = turn.failure_message = None
            repo.add_job(
                session,
                run_id=run.id,
                kind=DISCOVERY_JOB,
                payload={"turn": turn.number, "tries": turn.tries},
                dedupe_key=turn_job_key(run.id, turn.number, turn.tries),
                max_deliveries=self._max_deliveries,
                now=now,
            )
            repo.append_event(
                session,
                run,
                RunEventType.TURN_QUEUED,
                {"turn": turn.number, "trigger": "retry", "try": turn.tries},
                now,
            )
            self._audit(session, user_id, "requirements.turn-retried", run, {"turn": turn.number, "try": turn.tries})
            return self._detail(session, run)

    def submit(self, user_id: uuid.UUID, session_id: uuid.UUID, version: int) -> SessionDetail:
        now = self._clock()
        with transaction(self._factory) as session:
            run = self._require(session, user_id, session_id, lock=True)
            latest = req_repo.latest_version(session, run.id)
            if run.state == RunState.AWAITING_APPROVAL and latest is not None and latest.version == version:
                return self._detail(session, run)  # submitted twice: idempotent
            if run.state != RunState.READY_FOR_REVIEW:
                raise ApiError(
                    "conflict", "Only a version the analyst marked ready can be submitted. Answer the open questions."
                )
            if latest is None or latest.version != version:
                raise ApiError("conflict", "This is not the latest requirements version. Reload and review it again.")
            document = RequirementsDocument.model_validate(latest.content)
            blockers = readiness_blockers(document, question_states(session, run.id))
            if not document.readiness.ready or blockers:
                raise ApiError("conflict", "This version is not ready for approval.", details=blockers)
            latest.frozen_at = now
            repo.close_pending_approvals(session, run.id, ApprovalStatus.SUPERSEDED, now)
            approval = repo.add_approval(
                session,
                run_id=run.id,
                plan_version=version,
                gate=REQUIREMENTS_GATE,
                status=ApprovalStatus.PENDING.value,
                created_at=now,
            )
            repo.append_event(
                session,
                run,
                RunEventType.APPROVAL_REQUESTED,
                {"approval_id": str(approval.id), "version": version, "gate": REQUIREMENTS_GATE},
                now,
            )
            transition(session, run, RunState.AWAITING_APPROVAL, now, {"version": version})
            self._audit(
                session,
                user_id,
                "requirements.submitted",
                run,
                {"version": version, "content_sha256": latest.content_sha256},
            )
            return self._detail(session, run)

    def decide(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        approval_id: uuid.UUID,
        *,
        decision: RequirementsDecision,
        version: int,
        comment: str | None,
    ) -> SessionDetail:
        comment = (comment or "").strip() or None
        if decision == RequirementsDecision.REQUEST_CHANGES and not comment:
            raise ApiError("validation", "Describe what should change when requesting changes.")
        now = self._clock()
        with transaction(self._factory) as session:
            run = self._require(session, user_id, session_id, lock=True)
            approval = repo.get_approval(session, run.id, approval_id, lock=True)
            if approval is None or approval.gate != REQUIREMENTS_GATE:
                raise ApiError("not-found", "This approval request does not exist.")
            if approval.plan_version != version:
                raise ApiError(
                    "conflict", "This approval is for a different requirements version. Reload and decide again."
                )
            approve = decision == RequirementsDecision.APPROVE
            target_status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REVISION_REQUESTED
            if approval.status != ApprovalStatus.PENDING:
                if approval.status == target_status:
                    return self._detail(session, run)  # the same decision twice: idempotent
                raise ApiError("conflict", f"This version was already {approval.status.replace('-', ' ')}.")
            latest = req_repo.latest_version(session, run.id)
            if latest is None or latest.version != version or latest.frozen_at is None:
                raise ApiError("conflict", "This approval is for a version that is no longer current.")

            approval.status = target_status.value
            approval.decided_by = user_id
            approval.decided_at = now
            approval.comment = comment
            repo.append_event(
                session,
                run,
                RunEventType.APPROVAL_DECIDED,
                {"approval_id": str(approval.id), "decision": decision.value, "version": version},
                now,
            )
            if approve:
                latest.approved_at = now
                latest.approved_by = user_id
                transition(session, run, RunState.APPROVED, now, {"version": version})
                self._audit(
                    session,
                    user_id,
                    "requirements.approved",
                    run,
                    {"version": version, "version_id": str(latest.id), "content_sha256": latest.content_sha256},
                )
            else:
                transition(session, run, RunState.NEEDS_CHANGES, now, {"version": version})
                turn = req_repo.latest_turn(session, run.id)
                self._queue_turn(session, run, user_id, (turn.number if turn else 0) + 1, "revision", now, comment)
                self._audit(session, user_id, "requirements.changes-requested", run, {"version": version})
            return self._detail(session, run)

    def cancel(self, user_id: uuid.UUID, session_id: uuid.UUID) -> SessionDetail:
        now = self._clock()
        with transaction(self._factory) as session:
            run = self._require(session, user_id, session_id, lock=True)
            if run.state == RunState.CANCELLED:
                return self._detail(session, run)
            if RunState(run.state) in TERMINAL_STATES:
                raise ApiError("conflict", f"This session already finished ({run.state}) and cannot be cancelled.")
            transition(session, run, RunState.CANCELLED, now)
            repo.close_pending_approvals(session, run.id, ApprovalStatus.CANCELLED, now)
            repo.cancel_open_jobs(session, run.id)
            turn = req_repo.latest_turn(session, run.id)
            if turn is not None and turn.status in (TurnStatus.QUEUED, TurnStatus.RUNNING):
                turn.status = TurnStatus.CANCELLED.value
            self._audit(session, user_id, "requirements.cancelled", run)
            return self._detail(session, run)

    # --- versions -------------------------------------------------------------------------

    def versions(self, user_id: uuid.UUID, session_id: uuid.UUID) -> list[RequirementsVersion]:
        with transaction(self._factory) as session:
            run = self._require(session, user_id, session_id)
            return req_repo.list_versions(session, run.id)

    def version(
        self, user_id: uuid.UUID, session_id: uuid.UUID, number: int, diff_from: int | None = None
    ) -> tuple[RequirementsVersion, DocumentDiff | None, int | None]:
        with transaction(self._factory) as session:
            run = self._require(session, user_id, session_id)
            found = req_repo.get_version(session, run.id, number)
            if found is None:
                raise ApiError("not-found", f"Version {number} does not exist in this session.")
            if diff_from is None:
                return found, None, None
            other = req_repo.get_version(session, run.id, diff_from)
            if other is None:
                raise ApiError("not-found", f"Version {diff_from} does not exist in this session.")
            diff = diff_documents(
                RequirementsDocument.model_validate(other.content), RequirementsDocument.model_validate(found.content)
            )
            return found, diff, diff_from

    def approved(self, user_id: uuid.UUID, project_id: str) -> RequirementsVersion:
        pid = parse_project_id(project_id)
        with transaction(self._factory) as session:
            if projects_repo.get_owned_project(session, pid, user_id) is None:
                raise ApiError("not-found", "This project no longer exists.")
            found = req_repo.latest_approved_for_project(session, pid)
            if found is None:
                raise ApiError("not-found", "This project has no approved requirements yet.")
            return found
