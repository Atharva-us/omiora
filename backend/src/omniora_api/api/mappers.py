"""ORM rows → transport schemas."""

from __future__ import annotations

from ..db.models import (
    AgentAttempt,
    Approval,
    EngineeringTask,
    PlanVersion,
    Project,
    ProjectHistory,
    ProjectNote,
    Run,
    RunEvent,
    User,
)
from ..services.runs import RunDetail
from .schemas import (
    ApprovalOut,
    AttemptOut,
    AuthUserOut,
    HistoryOut,
    NoteOut,
    PlanContentOut,
    PlanOut,
    ProjectOut,
    RunDetailOut,
    RunEventOut,
    RunOut,
    TaskOut,
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
    )


def event_out(event: RunEvent) -> RunEventOut:
    return RunEventOut(seq=event.seq, type=event.type, data=event.data, at=iso(event.at))
