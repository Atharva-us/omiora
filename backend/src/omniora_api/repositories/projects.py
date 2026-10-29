from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select, tuple_
from sqlalchemy.orm import Session

from ..db.models import Project, ProjectHistory, ProjectNote


def add_project(session: Session, *, owner_id: uuid.UUID, configuration: dict[str, Any], now: datetime) -> Project:
    project = Project(
        owner_id=owner_id, status="configured", configuration=configuration, created_at=now, updated_at=now
    )
    session.add(project)
    session.flush()
    return project


def get_owned_project(
    session: Session, project_id: uuid.UUID, owner_id: uuid.UUID, *, lock: bool = False
) -> Project | None:
    query = select(Project).where(Project.id == project_id, Project.owner_id == owner_id)
    if lock:
        query = query.with_for_update()
    return session.scalar(query)


def list_owned_projects(
    session: Session, owner_id: uuid.UUID, *, limit: int, after: tuple[datetime, uuid.UUID] | None
) -> list[Project]:
    """Keyset pagination ordered by (updated_at DESC, id DESC)."""
    query = select(Project).where(Project.owner_id == owner_id)
    if after is not None:
        query = query.where(tuple_(Project.updated_at, Project.id) < tuple_(after[0], after[1]))
    return list(session.scalars(query.order_by(Project.updated_at.desc(), Project.id.desc()).limit(limit)))


def delete_project(session: Session, project: Project) -> None:
    session.execute(delete(Project).where(Project.id == project.id))


def add_history(session: Session, project_id: uuid.UUID, summary: str, now: datetime) -> None:
    session.add(ProjectHistory(project_id=project_id, summary=summary, at=now))


def list_history(session: Session, project_id: uuid.UUID) -> list[ProjectHistory]:
    # uuid7 ids increase with creation order, which breaks timestamp ties deterministically.
    return list(
        session.scalars(
            select(ProjectHistory)
            .where(ProjectHistory.project_id == project_id)
            .order_by(ProjectHistory.at.desc(), ProjectHistory.id.desc())
        )
    )


def add_note(session: Session, project_id: uuid.UUID, content: str, now: datetime) -> ProjectNote:
    note = ProjectNote(project_id=project_id, content=content, at=now)
    session.add(note)
    session.flush()
    return note


def list_notes(session: Session, project_id: uuid.UUID) -> list[ProjectNote]:
    return list(
        session.scalars(
            select(ProjectNote).where(ProjectNote.project_id == project_id).order_by(ProjectNote.at, ProjectNote.id)
        )
    )
