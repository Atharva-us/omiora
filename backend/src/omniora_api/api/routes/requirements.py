"""Requirements Analyst routes. A session id is a run id, so live progress uses the existing
`GET /runs/{id}/events` stream (and `/events/history`)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Path, Query, Response

from ...services.requirements import AnswerInput
from ..deps import Container, current_user, get_container
from ..mappers import (
    requirements_session_detail_out,
    requirements_session_out,
    requirements_version_out,
    requirements_version_summary_out,
)
from ..schemas import (
    AnswersIn,
    ApprovedRequirementsOut,
    RequirementsDecisionIn,
    RequirementsSessionDetailOut,
    RequirementsSessionOut,
    RequirementsVersionOut,
    RequirementsVersionSummaryOut,
    SubmitIn,
)

router = APIRouter(tags=["requirements"])

IdempotencyKey = Header(alias="Idempotency-Key", min_length=8, max_length=100)
VersionNumber = Path(ge=1, le=100_000)


@router.post("/projects/{project_id}/requirements-sessions", response_model=RequirementsSessionOut, status_code=202)
def start_session(
    project_id: str,
    response: Response,
    idempotency_key: str = IdempotencyKey,
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> RequirementsSessionOut:
    run, created = container.requirements.start(user.id, project_id, idempotency_key)
    if not created:
        response.status_code = 200
    return requirements_session_out(run)


@router.get("/projects/{project_id}/requirements-sessions", response_model=list[RequirementsSessionOut])
def list_sessions(
    project_id: str, user=Depends(current_user), container: Container = Depends(get_container)
) -> list[RequirementsSessionOut]:
    return [requirements_session_out(run) for run in container.requirements.list_for_project(user.id, project_id)]


@router.get("/projects/{project_id}/requirements/approved", response_model=ApprovedRequirementsOut)
def approved_requirements(
    project_id: str, user=Depends(current_user), container: Container = Depends(get_container)
) -> ApprovedRequirementsOut:
    version = container.requirements.approved(user.id, project_id)
    return ApprovedRequirementsOut(session_id=str(version.run_id), version=requirements_version_out(version))


@router.get("/requirements-sessions/{session_id}", response_model=RequirementsSessionDetailOut)
def get_session(
    session_id: uuid.UUID, user=Depends(current_user), container: Container = Depends(get_container)
) -> RequirementsSessionDetailOut:
    return requirements_session_detail_out(container.requirements.detail(user.id, session_id))


@router.post("/requirements-sessions/{session_id}/answers", response_model=RequirementsSessionDetailOut)
def submit_answers(
    session_id: uuid.UUID,
    body: AnswersIn,
    idempotency_key: str = IdempotencyKey,
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> RequirementsSessionDetailOut:
    answers = [AnswerInput(a.question_key, a.value, a.unknown) for a in body.answers]
    detail = container.requirements.answer(user.id, session_id, idempotency_key, answers, advance=body.advance)
    return requirements_session_detail_out(detail)


@router.post("/requirements-sessions/{session_id}/turns/retry", response_model=RequirementsSessionDetailOut)
def retry_turn(
    session_id: uuid.UUID, user=Depends(current_user), container: Container = Depends(get_container)
) -> RequirementsSessionDetailOut:
    return requirements_session_detail_out(container.requirements.retry_turn(user.id, session_id))


@router.post("/requirements-sessions/{session_id}/submit", response_model=RequirementsSessionDetailOut)
def submit_for_approval(
    session_id: uuid.UUID, body: SubmitIn, user=Depends(current_user), container: Container = Depends(get_container)
) -> RequirementsSessionDetailOut:
    return requirements_session_detail_out(container.requirements.submit(user.id, session_id, body.version))


@router.post("/requirements-sessions/{session_id}/approvals/{approval_id}", response_model=RequirementsSessionDetailOut)
def decide(
    session_id: uuid.UUID,
    approval_id: uuid.UUID,
    body: RequirementsDecisionIn,
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> RequirementsSessionDetailOut:
    detail = container.requirements.decide(
        user.id, session_id, approval_id, decision=body.decision, version=body.version, comment=body.comment
    )
    return requirements_session_detail_out(detail)


@router.post("/requirements-sessions/{session_id}/cancel", response_model=RequirementsSessionDetailOut)
def cancel_session(
    session_id: uuid.UUID, user=Depends(current_user), container: Container = Depends(get_container)
) -> RequirementsSessionDetailOut:
    return requirements_session_detail_out(container.requirements.cancel(user.id, session_id))


@router.get("/requirements-sessions/{session_id}/versions", response_model=list[RequirementsVersionSummaryOut])
def list_versions(
    session_id: uuid.UUID, user=Depends(current_user), container: Container = Depends(get_container)
) -> list[RequirementsVersionSummaryOut]:
    return [requirements_version_summary_out(v) for v in container.requirements.versions(user.id, session_id)]


@router.get("/requirements-sessions/{session_id}/versions/{version}", response_model=RequirementsVersionOut)
def get_version(
    session_id: uuid.UUID,
    version: int = VersionNumber,
    diff: int | None = Query(default=None, ge=1, le=100_000),
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> RequirementsVersionOut:
    found, changes, diff_from = container.requirements.version(user.id, session_id, version, diff)
    return requirements_version_out(found, changes, diff_from)
