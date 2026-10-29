from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from ..db.models import DiscoveryAnswer, DiscoveryQuestion, DiscoveryTurn, RequirementsVersion


def add_turn(session: Session, **values: Any) -> DiscoveryTurn:
    turn = DiscoveryTurn(**values)
    session.add(turn)
    session.flush()
    return turn


def get_turn(session: Session, run_id: uuid.UUID, number: int, *, lock: bool = False) -> DiscoveryTurn | None:
    query = select(DiscoveryTurn).where(DiscoveryTurn.run_id == run_id, DiscoveryTurn.number == number)
    if lock:
        query = query.with_for_update()
    return session.scalar(query)


def latest_turn(session: Session, run_id: uuid.UUID) -> DiscoveryTurn | None:
    return session.scalar(
        select(DiscoveryTurn).where(DiscoveryTurn.run_id == run_id).order_by(DiscoveryTurn.number.desc()).limit(1)
    )


def count_turns_created_since(session: Session, user_id: uuid.UUID, since: datetime) -> int:
    query = select(func.count()).where(DiscoveryTurn.created_by == user_id, DiscoveryTurn.created_at >= since)
    return session.scalar(query) or 0


def add_questions(session: Session, questions: list[DiscoveryQuestion]) -> None:
    session.add_all(questions)
    session.flush()


def list_questions(session: Session, run_id: uuid.UUID) -> list[DiscoveryQuestion]:
    return list(
        session.scalars(
            select(DiscoveryQuestion)
            .where(DiscoveryQuestion.run_id == run_id)
            .order_by(DiscoveryQuestion.turn_number, DiscoveryQuestion.created_at, DiscoveryQuestion.key)
        )
    )


def count_questions(session: Session, run_id: uuid.UUID) -> int:
    return session.scalar(select(func.count()).where(DiscoveryQuestion.run_id == run_id)) or 0


def add_answers(session: Session, answers: list[DiscoveryAnswer]) -> None:
    session.add_all(answers)
    session.flush()


def latest_answers(session: Session, run_id: uuid.UUID) -> dict[uuid.UUID, DiscoveryAnswer]:
    """The current answer per question: the newest row (ids are time-ordered UUIDv7)."""
    rows = session.scalars(
        select(DiscoveryAnswer)
        .where(DiscoveryAnswer.run_id == run_id)
        .order_by(DiscoveryAnswer.question_id, DiscoveryAnswer.created_at.desc(), DiscoveryAnswer.id.desc())
        .ext(distinct_on(DiscoveryAnswer.question_id))
    )
    return {row.question_id: row for row in rows}


def submission_exists(session: Session, run_id: uuid.UUID, idempotency_key: str) -> bool:
    query = select(DiscoveryAnswer.id).where(
        DiscoveryAnswer.run_id == run_id, DiscoveryAnswer.idempotency_key == idempotency_key
    )
    return session.scalar(query.limit(1)) is not None


def add_version(session: Session, **values: Any) -> RequirementsVersion:
    version = RequirementsVersion(**values)
    session.add(version)
    session.flush()
    return version


def get_version(session: Session, run_id: uuid.UUID, version: int) -> RequirementsVersion | None:
    return session.scalar(
        select(RequirementsVersion).where(RequirementsVersion.run_id == run_id, RequirementsVersion.version == version)
    )


def latest_version(session: Session, run_id: uuid.UUID) -> RequirementsVersion | None:
    return session.scalar(
        select(RequirementsVersion)
        .where(RequirementsVersion.run_id == run_id)
        .order_by(RequirementsVersion.version.desc())
        .limit(1)
    )


def list_versions(session: Session, run_id: uuid.UUID) -> list[RequirementsVersion]:
    return list(
        session.scalars(
            select(RequirementsVersion)
            .where(RequirementsVersion.run_id == run_id)
            .order_by(RequirementsVersion.version)
        )
    )


def get_version_by_id(session: Session, version_id: uuid.UUID) -> RequirementsVersion | None:
    return session.get(RequirementsVersion, version_id)


def latest_approved_for_project(session: Session, project_id: uuid.UUID) -> RequirementsVersion | None:
    return session.scalar(
        select(RequirementsVersion)
        .where(RequirementsVersion.project_id == project_id, RequirementsVersion.approved_at.is_not(None))
        .order_by(RequirementsVersion.approved_at.desc(), RequirementsVersion.id.desc())
        .limit(1)
    )
