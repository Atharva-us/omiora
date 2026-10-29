"""ORM rows → transport schemas."""

from __future__ import annotations

from ..db.models import (
    AgentAttempt,
    Approval,
    DiscoveryTurn,
    EngineeringTask,
    PlanVersion,
    Project,
    ProjectHistory,
    ProjectNote,
    RequirementsVersion,
    Run,
    RunEvent,
    User,
)
from ..domain.requirements import DocumentDiff, RequirementsDocument
from ..services.requirements import QuestionView, SessionDetail
from ..services.runs import RunDetail
from .schemas import (
    AnswerOut,
    ApprovalOut,
    AttemptOut,
    AuthUserOut,
    HistoryOut,
    NoteOut,
    PinnedRequirementsOut,
    PlanContentOut,
    PlanOut,
    ProjectOut,
    QuestionOut,
    RequirementsApprovalOut,
    RequirementsDocumentOut,
    RequirementsSessionDetailOut,
    RequirementsSessionOut,
    RequirementsVersionOut,
    RequirementsVersionSummaryOut,
    RunDetailOut,
    RunEventOut,
    RunOut,
    TaskOut,
    TurnAttemptOut,
    TurnOut,
    VersionDiffOut,
    iso,
)


def user_out(user: User) -> AuthUserOut:
    return AuthUserOut(id=str(user.id), email=user.email, name=user.name)


def project_out(project: Project) -> ProjectOut:
    return ProjectOut(
        id=str(project.id),
        source="user",
        status=project.status,
        configuration=project.configuration,
        created_at=iso(project.created_at),
        updated_at=iso(project.updated_at),
    )


def note_out(note: ProjectNote) -> NoteOut:
    return NoteOut(id=str(note.id), content=note.content, at=iso(note.at))


def history_out(entry: ProjectHistory) -> HistoryOut:
    return HistoryOut(id=str(entry.id), project_id=str(entry.project_id), at=iso(entry.at), summary=entry.summary)


def run_out(run: Run) -> RunOut:
    return RunOut(
        id=str(run.id),
        project_id=str(run.project_id),
        agent_role=run.agent_role,
        state=run.state,
        current_plan_version=run.current_plan_version,
        failure_code=run.failure_code,
        failure_message=run.failure_message,
        last_event_seq=run.event_seq,
        pinned_requirements_version_id=str(run.pinned_requirements_version_id)
        if run.pinned_requirements_version_id
        else None,
        requirements_skipped=run.requirements_skipped,
        created_at=iso(run.created_at),
        updated_at=iso(run.updated_at),
    )


def plan_out(plan: PlanVersion) -> PlanOut:
    content = {key: value for key, value in plan.content.items() if key != "tasks"}  # tasks are served from their table
    return PlanOut(
        version=plan.version, created_at=iso(plan.created_at), content=PlanContentOut.model_validate(content)
    )


def task_out(task: EngineeringTask) -> TaskOut:
    return TaskOut(
        key=task.key,
        title=task.title,
        description=task.description,
        acceptance_criteria=task.acceptance_criteria,
        depends_on=task.depends_on,
        requirement_ids=task.requirement_ids,
        suggested_agent=task.suggested_agent,
        status="proposed",
    )


def approval_out(approval: Approval) -> ApprovalOut:
    return ApprovalOut(
        id=str(approval.id),
        plan_version=approval.plan_version,
        gate=approval.gate,
        status=approval.status,
        comment=approval.comment,
        decided_at=iso(approval.decided_at) if approval.decided_at else None,
        created_at=iso(approval.created_at),
    )


def attempt_out(attempt: AgentAttempt) -> AttemptOut:
    return AttemptOut(
        attempt=attempt.attempt,
        plan_version=attempt.plan_version,
        outcome=attempt.outcome,
        provider=attempt.provider,
        model=attempt.model,
        input_tokens=attempt.input_tokens,
        output_tokens=attempt.output_tokens,
        latency_ms=attempt.latency_ms,
        error_code=attempt.error_code,
        error_message=attempt.error_message,
        validation_errors=list(attempt.validation_errors),
        created_at=iso(attempt.created_at),
    )


def run_detail_out(detail: RunDetail) -> RunDetailOut:
    return RunDetailOut(
        run=run_out(detail.run),
        plan=plan_out(detail.plan) if detail.plan else None,
        tasks=[task_out(task) for task in detail.tasks],
        approvals=[approval_out(approval) for approval in detail.approvals],
        attempts=[attempt_out(attempt) for attempt in detail.attempts],
        requirements=PinnedRequirementsOut(
            version_id=str(detail.requirements.id),
            session_id=str(detail.requirements.run_id),
            version=detail.requirements.version,
            content_sha256=detail.requirements.content_sha256,
        )
        if detail.requirements
        else None,
    )


def event_out(event: RunEvent) -> RunEventOut:
    return RunEventOut(seq=event.seq, type=event.type, data=event.data, at=iso(event.at))


# --- requirements analyst -----------------------------------------------------------------


def _optional_iso(value) -> str | None:
    return iso(value) if value else None


def requirements_version_summary_out(version: RequirementsVersion) -> RequirementsVersionSummaryOut:
    document = RequirementsDocument.model_validate(version.content)
    return RequirementsVersionSummaryOut(
        id=str(version.id),
        version=version.version,
        parent_version_id=str(version.parent_version_id) if version.parent_version_id else None,
        content_sha256=version.content_sha256,
        turn_number=version.turn_number,
        created_at=iso(version.created_at),
        frozen_at=_optional_iso(version.frozen_at),
        approved_at=_optional_iso(version.approved_at),
        requirement_count=len(document.active()),
        must_count=sum(1 for r in document.active() if r.priority == "must"),
        ready=document.readiness.ready,
    )


def requirements_version_out(
    version: RequirementsVersion, diff: DocumentDiff | None = None, diff_from: int | None = None
) -> RequirementsVersionOut:
    summary = requirements_version_summary_out(version)
    diff_out = None
    if diff is not None and diff_from is not None:
        diff_out = VersionDiffOut(
            from_version=diff_from,
            added=diff.added,
            deprecated=diff.deprecated,
            changed=[{"id": change.id, "fields": change.fields} for change in diff.changed],
            context_fields=diff.context_fields,
        )
    return RequirementsVersionOut(
        **summary.model_dump(),
        content=RequirementsDocumentOut.model_validate(version.content),
        diff=diff_out,
    )


def requirements_session_out(run: Run) -> RequirementsSessionOut:
    return RequirementsSessionOut(
        id=str(run.id),
        project_id=str(run.project_id),
        state=run.state,
        failure_code=run.failure_code,
        failure_message=run.failure_message,
        last_event_seq=run.event_seq,
        created_at=iso(run.created_at),
        updated_at=iso(run.updated_at),
    )


def turn_out(turn: DiscoveryTurn) -> TurnOut:
    return TurnOut(
        number=turn.number,
        status=turn.status,
        trigger=turn.trigger,
        tries=turn.tries,
        failure_code=turn.failure_code,
        failure_message=turn.failure_message,
        requirements_version=turn.requirements_version,
        created_at=iso(turn.created_at),
        completed_at=_optional_iso(turn.completed_at),
    )


def question_out(view: QuestionView) -> QuestionOut:
    q, answer = view.question, view.answer
    return QuestionOut(
        key=q.key,
        turn_number=q.turn_number,
        prompt=q.prompt,
        why=q.why,
        kind=q.kind,
        options=list(q.options),
        blocking=q.blocking,
        topic=q.topic,
        relates_to=list(q.relates_to),
        status=q.status,
        answer=AnswerOut(value=answer.value.get("value"), unknown=answer.unknown, answered_at=iso(answer.created_at))
        if answer
        else None,
    )


def requirements_approval_out(approval: Approval) -> RequirementsApprovalOut:
    return RequirementsApprovalOut(
        id=str(approval.id),
        version=approval.plan_version,
        gate=approval.gate,
        status=approval.status,
        comment=approval.comment,
        decided_at=_optional_iso(approval.decided_at),
        created_at=iso(approval.created_at),
    )


def turn_attempt_out(attempt: AgentAttempt) -> TurnAttemptOut:
    return TurnAttemptOut(
        turn=attempt.plan_version,
        attempt=attempt.attempt,
        outcome=attempt.outcome,
        provider=attempt.provider,
        model=attempt.model,
        input_tokens=attempt.input_tokens,
        output_tokens=attempt.output_tokens,
        latency_ms=attempt.latency_ms,
        error_code=attempt.error_code,
        error_message=attempt.error_message,
        validation_errors=list(attempt.validation_errors),
        created_at=iso(attempt.created_at),
    )


def requirements_session_detail_out(detail: SessionDetail) -> RequirementsSessionDetailOut:
    return RequirementsSessionDetailOut(
        session=requirements_session_out(detail.run),
        turn=turn_out(detail.turn) if detail.turn else None,
        max_turns=detail.max_turns,
        questions=[question_out(view) for view in detail.questions],
        version=requirements_version_out(detail.version) if detail.version else None,
        approvals=[requirements_approval_out(a) for a in detail.approvals],
        attempts=[turn_attempt_out(a) for a in detail.attempts],
    )
