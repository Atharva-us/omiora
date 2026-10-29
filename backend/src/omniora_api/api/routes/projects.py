from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response

from ...domain.projects import ProjectConfiguration
from ...services.samples import SAMPLE_PROJECTS
from ..deps import Container, current_user, get_container
from ..mappers import history_out, note_out, project_out
from ..schemas import HistoryOut, NoteIn, NoteOut, ProjectOut, ProjectPageOut, ProjectUpdateIn

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/samples")
def samples() -> list[dict[str, Any]]:
    return SAMPLE_PROJECTS


@router.get("", response_model=ProjectPageOut)
def list_projects(
    cursor: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=50, ge=1, le=100),
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> ProjectPageOut:
    page = container.projects.list(user.id, limit=limit, cursor=cursor)
    return ProjectPageOut(items=[project_out(p) for p in page.items], next_cursor=page.next_cursor)


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    body: ProjectConfiguration, user=Depends(current_user), container: Container = Depends(get_container)
) -> ProjectOut:
    return project_out(container.projects.create(user.id, body))


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, user=Depends(current_user), container: Container = Depends(get_container)) -> Any:
    for sample in SAMPLE_PROJECTS:
        if sample["id"] == project_id:
            return sample
    return project_out(container.projects.get(user.id, project_id))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: str, body: ProjectUpdateIn, user=Depends(current_user), container: Container = Depends(get_container)
) -> ProjectOut:
    project = container.projects.update(user.id, project_id, name=body.name, configuration=body.configuration)
    return project_out(project)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: str, user=Depends(current_user), container: Container = Depends(get_container)
) -> Response:
    container.projects.delete(user.id, project_id)
    return Response(status_code=204)


@router.get("/{project_id}/history", response_model=list[HistoryOut])
def history(
    project_id: str, user=Depends(current_user), container: Container = Depends(get_container)
) -> list[HistoryOut]:
    return [history_out(entry) for entry in container.projects.history(user.id, project_id)]


@router.get("/{project_id}/notes", response_model=list[NoteOut])
def notes(project_id: str, user=Depends(current_user), container: Container = Depends(get_container)) -> list[NoteOut]:
    return [note_out(note) for note in container.projects.notes(user.id, project_id)]


@router.post("/{project_id}/notes", response_model=NoteOut, status_code=201)
def add_note(
    project_id: str, body: NoteIn, user=Depends(current_user), container: Container = Depends(get_container)
) -> NoteOut:
    return note_out(container.projects.add_note(user.id, project_id, body.content))
