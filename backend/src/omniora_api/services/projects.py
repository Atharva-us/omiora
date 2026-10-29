"""Projects use cases. Behaviour matches the frontend `ProjectService` contract
(`src/test/contracts/project-service.contract.ts`)."""

from __future__ import annotations

import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from ..audit import append_audit
from ..db.models import Project, ProjectHistory, ProjectNote
from ..db.session import SessionFactory, transaction
from ..domain.projects import (
    ProjectConfiguration,
    configuration_problems,
    normalize_configuration,
    validate_note,
    validate_project_name,
)
from ..errors import ApiError
from ..repositories import projects as repo
from . import Clock, utcnow
from .samples import SAMPLE_IDS

PAGE_MAX = 100


@dataclass(frozen=True)
class ProjectPage:
    items: list[Project]
    next_cursor: str | None


def _encode_cursor(project: Project) -> str:
    raw = json.dumps({"u": project.updated_at.isoformat(), "i": str(project.id)}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        data = json.loads(raw)
        return datetime.fromisoformat(data["u"]), uuid.UUID(data["i"])
    except (binascii.Error, ValueError, KeyError, TypeError) as exc:
        raise ApiError("validation", "The pagination cursor is not valid.") from exc


def _validated(configuration: ProjectConfiguration) -> ProjectConfiguration:
    normalized = normalize_configuration(configuration)
    problems = configuration_problems(normalized)
    if problems:
        raise ApiError("validation", "The project configuration is not valid.", details=problems)
    return normalized


def parse_project_id(project_id: str) -> uuid.UUID:
    """Sample ids are read-only; anything that is not a UUID cannot exist."""
    if project_id in SAMPLE_IDS:
        raise ApiError("read-only", "Sample projects are read-only.")
    try:
        return uuid.UUID(project_id)
    except ValueError:
        raise ApiError("not-found", "This project no longer exists.") from None


class ProjectsService:
    def __init__(self, factory: SessionFactory, clock: Clock = utcnow) -> None:
        self._factory = factory
        self._clock = clock

    def _require(self, session, owner_id: uuid.UUID, project_id: str, *, lock: bool = False) -> Project:
        project = repo.get_owned_project(session, parse_project_id(project_id), owner_id, lock=lock)
        if project is None:  # absent or owned by someone else: indistinguishable on purpose
            raise ApiError("not-found", "This project no longer exists.")
        return project

    def create(self, owner_id: uuid.UUID, configuration: ProjectConfiguration) -> Project:
        valid = _validated(configuration)
        now = self._clock()
        with transaction(self._factory) as session:
            project = repo.add_project(session, owner_id=owner_id, configuration=valid.model_dump(mode="json"), now=now)
            repo.add_history(session, project.id, "Project created from the configuration wizard.", now)
            append_audit(
                session,
                actor_type="user",
                actor_id=str(owner_id),
                action="project.created",
                entity_type="project",
                entity_id=str(project.id),
            )
            return project

    def list(self, owner_id: uuid.UUID, *, limit: int, cursor: str | None) -> ProjectPage:
        limit = max(1, min(limit, PAGE_MAX))
        after = _decode_cursor(cursor) if cursor else None
        with transaction(self._factory) as session:
            rows = repo.list_owned_projects(session, owner_id, limit=limit + 1, after=after)
        has_more = len(rows) > limit
        items = rows[:limit]
        return ProjectPage(items=items, next_cursor=_encode_cursor(items[-1]) if has_more else None)

    def get(self, owner_id: uuid.UUID, project_id: str) -> Project:
        with transaction(self._factory) as session:
            return self._require(session, owner_id, project_id)

    def update(
        self, owner_id: uuid.UUID, project_id: str, *, name: str | None, configuration: ProjectConfiguration | None
    ) -> Project:
        now = self._clock()
        with transaction(self._factory) as session:
            project = self._require(session, owner_id, project_id, lock=True)
            current = ProjectConfiguration.model_validate(project.configuration)
            changes: list[str] = []
            if configuration is not None:
                current = _validated(configuration)
                changes.append("Configuration updated.")
            if name is not None:
                problem = validate_project_name(name)
                if problem:
                    raise ApiError("validation", "The project name is not valid.", details=[problem])
                if name.strip() != project.configuration["name"]:
                    changes.append(f'Renamed to "{name.strip()}".')
                current = current.model_copy(update={"name": name.strip()})
            if not changes:
                return project
            project.configuration = current.model_dump(mode="json")
            project.updated_at = now
            for summary in changes:
                repo.add_history(session, project.id, summary, now)
            append_audit(
                session,
                actor_type="user",
                actor_id=str(owner_id),
                action="project.updated",
                entity_type="project",
                entity_id=str(project.id),
                data={"changes": len(changes)},
            )
            return project

    def delete(self, owner_id: uuid.UUID, project_id: str) -> None:
        with transaction(self._factory) as session:
            project = self._require(session, owner_id, project_id, lock=True)
            repo.delete_project(session, project)
            append_audit(
                session,
                actor_type="user",
                actor_id=str(owner_id),
                action="project.deleted",
                entity_type="project",
                entity_id=str(project.id),
            )

    def history(self, owner_id: uuid.UUID, project_id: str) -> list[ProjectHistory]:
        if project_id in SAMPLE_IDS:
            return []
        with transaction(self._factory) as session:
            project = self._require(session, owner_id, project_id)
            return repo.list_history(session, project.id)

    def notes(self, owner_id: uuid.UUID, project_id: str) -> list[ProjectNote]:
        if project_id in SAMPLE_IDS:
            return []
        with transaction(self._factory) as session:
            project = self._require(session, owner_id, project_id)
            return repo.list_notes(session, project.id)

    def add_note(self, owner_id: uuid.UUID, project_id: str, content: str) -> ProjectNote:
        problem = validate_note(content)
        if problem:
            raise ApiError("validation", "The note was not saved.", details=[problem])
        now = self._clock()
        with transaction(self._factory) as session:
            project = self._require(session, owner_id, project_id, lock=True)
            note = repo.add_note(session, project.id, content.strip(), now)
            project.updated_at = now
            repo.add_history(session, project.id, "Requirement note added.", now)
            return note
