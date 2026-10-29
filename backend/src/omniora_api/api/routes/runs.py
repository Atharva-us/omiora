from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.responses import StreamingResponse

from ...domain.runs import TERMINAL_STATES, RunState
from ...errors import ApiError
from ..deps import Container, current_user, get_container
from ..mappers import approval_out, event_out, run_detail_out, run_out
from ..schemas import ApprovalOut, DecisionIn, RunDetailOut, RunEventOut, RunOut, StartRunIn

router = APIRouter(tags=["runs"])


@router.post("/projects/{project_id}/runs", response_model=RunOut, status_code=202)
def start_run(
    project_id: str,
    response: Response,
    body: StartRunIn | None = None,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> RunOut:
    without_requirements = body.without_requirements if body else False
    run, created = container.runs.start(user.id, project_id, idempotency_key, without_requirements=without_requirements)
    if not created:
        response.status_code = 200
    return run_out(run)


@router.get("/projects/{project_id}/runs", response_model=list[RunOut])
def list_runs(
    project_id: str, user=Depends(current_user), container: Container = Depends(get_container)
) -> list[RunOut]:
    return [run_out(run) for run in container.runs.list_for_project(user.id, project_id)]


@router.get("/runs/{run_id}", response_model=RunDetailOut)
def get_run(
    run_id: uuid.UUID, user=Depends(current_user), container: Container = Depends(get_container)
) -> RunDetailOut:
    return run_detail_out(container.runs.detail(user.id, run_id))


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
def cancel_run(run_id: uuid.UUID, user=Depends(current_user), container: Container = Depends(get_container)) -> RunOut:
    return run_out(container.runs.cancel(user.id, run_id))


@router.get("/runs/{run_id}/approvals", response_model=list[ApprovalOut])
def list_approvals(
    run_id: uuid.UUID, user=Depends(current_user), container: Container = Depends(get_container)
) -> list[ApprovalOut]:
    return [approval_out(approval) for approval in container.runs.detail(user.id, run_id).approvals]


@router.post("/runs/{run_id}/approvals/{approval_id}", response_model=ApprovalOut)
def decide(
    run_id: uuid.UUID,
    approval_id: uuid.UUID,
    body: DecisionIn,
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> ApprovalOut:
    approval = container.runs.decide(
        user.id, run_id, approval_id, decision=body.decision, plan_version=body.plan_version, comment=body.comment
    )
    return approval_out(approval)


@router.get("/runs/{run_id}/events/history", response_model=list[RunEventOut])
def event_history(
    run_id: uuid.UUID,
    after: int = Query(default=0, ge=0),
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> list[RunEventOut]:
    container.runs.authorize(user.id, run_id)
    events, _ = container.runs.events(run_id, after)
    return [event_out(event) for event in events]


def _parse_last_event_id(header: str | None, query: int | None) -> int:
    if header:
        if not header.isdigit():
            raise ApiError("validation", "Last-Event-ID must be a non-negative integer.")
        return int(header)
    return query or 0


@router.get("/runs/{run_id}/events")
def stream_events(
    run_id: uuid.UUID,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID", max_length=20),
    after: int | None = Query(default=None, ge=0),
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> StreamingResponse:
    """Server-sent events. Each event's `id` is its per-run sequence number, so a reconnecting
    EventSource resumes exactly after the last event it received (`Last-Event-ID`). The stream
    closes after a terminal state has been delivered, or after `sse_max_stream_seconds`."""
    container.runs.authorize(user.id, run_id)
    cursor = _parse_last_event_id(last_event_id, after)
    settings = container.settings

    def generate() -> Iterator[str]:
        position = cursor
        started = last_beat = time.monotonic()
        yield "retry: 3000\n\n"
        while True:
            events, state = container.runs.events(run_id, position)
            for event in events:
                payload = event_out(event).model_dump(by_alias=True)
                yield f"id: {event.seq}\nevent: {event.type}\ndata: {json.dumps(payload)}\n\n"
                position = event.seq
            if not events and RunState(state) in TERMINAL_STATES:
                yield f"event: end\ndata: {json.dumps({'state': state})}\n\n"
                return
            now = time.monotonic()
            if now - started >= settings.sse_max_stream_seconds:
                return  # the client reconnects with Last-Event-ID
            if now - last_beat >= settings.sse_heartbeat_seconds:
                yield ": keep-alive\n\n"
                last_beat = now
            if not events:
                time.sleep(settings.sse_poll_seconds)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
