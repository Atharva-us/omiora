"""ORM models. The schema itself is owned by Alembic migrations; `tests/test_migrations.py`
fails if these models and the migrations drift apart."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..ids import uuid7


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSONB, list[Any]: JSONB}


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


ACTIVE_RUN_STATES_SQL = (
    "state IN ('queued', 'planning', 'awaiting-approval', 'discovering', 'ready-for-review', 'needs-changes')"
)
RUN_STATES_SQL = (
    "state IN ('queued','planning','awaiting-approval','approved','rejected','failed','cancelled',"
    "'discovering','ready-for-review','needs-changes')"
)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _now()
    __table_args__ = (Index("uq_users_email_lower", func.lower(email), unique=True),)


class AuthSession(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = _now()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = _pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("ix_projects_owner_updated", "owner_id", text("updated_at DESC"), text("id DESC")),)


class ProjectHistory(Base):
    __tablename__ = "project_history"
    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)


class ProjectNote(Base):
    __tablename__ = "project_notes"
    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[uuid.UUID] = _pk()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agent_role: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    current_plan_version: Mapped[int | None] = mapped_column(Integer)
    failure_code: Mapped[str | None] = mapped_column(String(64))
    failure_message: Mapped[str | None] = mapped_column(String(500))
    event_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    # Planning runs only: the exact approved requirements version the plan must follow, or an
    # explicit, recorded choice to plan without requirements. Both null/false on older runs.
    pinned_requirements_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requirements_versions.id", use_alter=True, name="fk_runs_pinned_requirements_version")
    )
    requirements_skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("project_id", "idempotency_key", name="uq_runs_project_idempotency"),
        Index(
            "uq_runs_one_active_per_project", "project_id", unique=True, postgresql_where=text(ACTIVE_RUN_STATES_SQL)
        ),
        Index("ix_runs_created_by_created_at", "created_by", "created_at"),
        Index("ix_runs_project_created", "project_id", text("created_at DESC")),
        CheckConstraint(RUN_STATES_SQL, name="ck_runs_state"),
        CheckConstraint("agent_role IN ('project-manager','requirements-analyst')", name="ck_runs_agent_role"),
    )


class RunEvent(Base):
    __tablename__ = "run_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_run_events_run_seq"),)


class PlanVersion(Base):
    __tablename__ = "plan_versions"
    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_attempts.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (UniqueConstraint("run_id", "version", name="uq_plan_versions_run_version"),)


class EngineeringTask(Base):
    __tablename__ = "engineering_tasks"
    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    key: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    acceptance_criteria: Mapped[list[Any]] = mapped_column(nullable=False)
    depends_on: Mapped[list[Any]] = mapped_column(nullable=False)
    requirement_ids: Mapped[list[Any]] = mapped_column(nullable=False)
    suggested_agent: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="proposed")
    __table_args__ = (
        UniqueConstraint("run_id", "plan_version", "key", name="uq_tasks_run_version_key"),
        CheckConstraint("status IN ('proposed')", name="ck_tasks_status"),
    )


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    # Version of the gated artifact: the plan version for gate "plan", the requirements version for
    # gate "requirements".
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    gate: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comment: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        Index("uq_approvals_one_pending_per_run", "run_id", unique=True, postgresql_where=text("status = 'pending'")),
    )


class AgentAttempt(Base):
    __tablename__ = "agent_attempts"
    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    # Plan version for planning runs; discovery turn number for requirements sessions.
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    request_id: Mapped[str | None] = mapped_column(String(100))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(500))
    validation_errors: Mapped[list[Any]] = mapped_column(nullable=False, server_default="[]")
    raw_output: Mapped[str | None] = mapped_column(Text)
    prompt_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    deliveries: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_deliveries: Mapped[int] = mapped_column(Integer, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        Index("ix_jobs_claimable", "status", "available_at"),
        CheckConstraint("status IN ('queued','leased','done','failed','cancelled')", name="ck_jobs_status"),
    )


class DiscoveryTurn(Base):
    """One Requirements Analyst turn. A failed turn keeps its number and is retried in place."""

    __tablename__ = "discovery_turns"
    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    trigger: Mapped[str] = mapped_column(String(24), nullable=False)
    tries: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    revision_comment: Mapped[str | None] = mapped_column(String(2000))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    failure_message: Mapped[str | None] = mapped_column(String(500))
    requirements_version: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("run_id", "number", name="uq_discovery_turns_run_number"),
        # At most one turn in flight per session: the guarantee behind "a turn advances once".
        Index(
            "uq_discovery_turns_one_open_per_run",
            "run_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        Index("ix_discovery_turns_created_by_created_at", "created_by", "created_at"),
        CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')", name="ck_discovery_turns_status"
        ),
        CheckConstraint(
            "trigger IN ('start','answers','more-questions','revision')", name="ck_discovery_turns_trigger"
        ),
    )


class DiscoveryQuestion(Base):
    __tablename__ = "discovery_questions"
    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    key: Mapped[str] = mapped_column(String(16), nullable=False)
    prompt: Mapped[str] = mapped_column(String(300), nullable=False)
    why: Mapped[str] = mapped_column(String(300), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    options: Mapped[list[Any]] = mapped_column(nullable=False)
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False)
    topic: Mapped[str] = mapped_column(String(24), nullable=False)
    relates_to: Mapped[list[Any]] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("run_id", "key", name="uq_discovery_questions_run_key"),
        CheckConstraint(
            "kind IN ('single-choice','multiple-choice','free-text','yes-no')", name="ck_discovery_questions_kind"
        ),
        CheckConstraint("status IN ('open','answered','withdrawn')", name="ck_discovery_questions_status"),
    )


class DiscoveryAnswer(Base):
    """Append-only. The newest row per question is the current answer; earlier rows are history."""

    __tablename__ = "discovery_answers"
    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("discovery_questions.id", ondelete="CASCADE"), nullable=False
    )
    value: Mapped[dict[str, Any]] = mapped_column(nullable=False)  # {"value": ...}; {"value": null} when unknown
    unknown: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("run_id", "idempotency_key", "question_id", name="uq_discovery_answers_submission"),
        Index("ix_discovery_answers_question_created", "question_id", "created_at"),
    )


class RequirementsVersion(Base):
    """An immutable requirements document. A trigger (migration 0002) rejects any change to its
    content, and any change to the freeze or approval stamps once they are set."""

    __tablename__ = "requirements_versions"
    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("requirements_versions.id"))
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    turn_number: Mapped[int | None] = mapped_column(Integer)
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_attempts.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    __table_args__ = (
        UniqueConstraint("run_id", "version", name="uq_requirements_versions_run_version"),
        Index("ix_requirements_versions_project_approved", "project_id", "approved_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
