"""requirements analyst: discovery sessions, questions, answers, versioned requirements

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-29

Discovery sessions are runs with agent_role 'requirements-analyst', so they reuse jobs, leases,
attempts, events, approvals, and the audit log. This migration adds their states, the discovery
tables, immutable requirements versions, and the planning-run pin to an approved version.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_STATES = "state IN ('queued','planning','awaiting-approval','approved','rejected','failed','cancelled')"
NEW_STATES = (
    "state IN ('queued','planning','awaiting-approval','approved','rejected','failed','cancelled',"
    "'discovering','ready-for-review','needs-changes')"
)
OLD_ACTIVE = "state IN ('queued', 'planning', 'awaiting-approval')"
NEW_ACTIVE = "state IN ('queued', 'planning', 'awaiting-approval', 'discovering', 'ready-for-review', 'needs-changes')"


def upgrade() -> None:
    op.create_table(
        "discovery_turns",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("trigger", sa.String(length=24), nullable=False),
        sa.Column("tries", sa.Integer(), server_default="1", nullable=False),
        sa.Column("revision_comment", sa.String(length=2000), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.String(length=500), nullable=True),
        sa.Column("requirements_version", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')", name="ck_discovery_turns_status"
        ),
        sa.CheckConstraint(
            "trigger IN ('start','answers','more-questions','revision')", name="ck_discovery_turns_trigger"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "number", name="uq_discovery_turns_run_number"),
    )
    op.create_index(
        "uq_discovery_turns_one_open_per_run",
        "discovery_turns",
        ["run_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_index(
        "ix_discovery_turns_created_by_created_at", "discovery_turns", ["created_by", "created_at"], unique=False
    )
    op.create_table(
        "discovery_questions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=16), nullable=False),
        sa.Column("prompt", sa.String(length=300), nullable=False),
        sa.Column("why", sa.String(length=300), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False),
        sa.Column("topic", sa.String(length=24), nullable=False),
        sa.Column("relates_to", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('single-choice','multiple-choice','free-text','yes-no')", name="ck_discovery_questions_kind"
        ),
        sa.CheckConstraint("status IN ('open','answered','withdrawn')", name="ck_discovery_questions_status"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "key", name="uq_discovery_questions_run_key"),
    )
    op.create_table(
        "discovery_answers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("unknown", sa.Boolean(), nullable=False),
        sa.Column("answered_by", sa.UUID(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["answered_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["question_id"], ["discovery_questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "idempotency_key", "question_id", name="uq_discovery_answers_submission"),
    )
    op.create_index(
        "ix_discovery_answers_question_created", "discovery_answers", ["question_id", "created_at"], unique=False
    )
    op.create_table(
        "requirements_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.UUID(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=True),
        sa.Column("attempt_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["attempt_id"], ["agent_attempts.id"]),
        sa.ForeignKeyConstraint(["parent_version_id"], ["requirements_versions.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "version", name="uq_requirements_versions_run_version"),
    )
    op.create_index(
        "ix_requirements_versions_project_approved",
        "requirements_versions",
        ["project_id", "approved_at"],
        unique=False,
    )

    op.add_column("runs", sa.Column("pinned_requirements_version_id", sa.UUID(), nullable=True))
    op.add_column(
        "runs", sa.Column("requirements_skipped", sa.Boolean(), server_default=sa.text("false"), nullable=False)
    )
    op.create_foreign_key(
        "fk_runs_pinned_requirements_version",
        "runs",
        "requirements_versions",
        ["pinned_requirements_version_id"],
        ["id"],
    )
    op.drop_constraint("ck_runs_state", "runs", type_="check")
    op.create_check_constraint("ck_runs_state", "runs", NEW_STATES)
    op.create_check_constraint("ck_runs_agent_role", "runs", "agent_role IN ('project-manager','requirements-analyst')")
    op.drop_index("uq_runs_one_active_per_project", table_name="runs", postgresql_where=sa.text(OLD_ACTIVE))
    op.create_index(
        "uq_runs_one_active_per_project", "runs", ["project_id"], unique=True, postgresql_where=sa.text(NEW_ACTIVE)
    )

    # Versions are immutable once written; freeze and approval stamps are write-once.
    op.execute(
        """
        CREATE FUNCTION requirements_versions_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.content IS DISTINCT FROM OLD.content
               OR NEW.content_sha256 IS DISTINCT FROM OLD.content_sha256
               OR NEW.version IS DISTINCT FROM OLD.version
               OR NEW.run_id IS DISTINCT FROM OLD.run_id
               OR NEW.project_id IS DISTINCT FROM OLD.project_id
               OR NEW.parent_version_id IS DISTINCT FROM OLD.parent_version_id
               OR NEW.schema_version IS DISTINCT FROM OLD.schema_version
               OR (OLD.frozen_at IS NOT NULL AND NEW.frozen_at IS DISTINCT FROM OLD.frozen_at)
               OR (OLD.approved_at IS NOT NULL AND NEW.approved_at IS DISTINCT FROM OLD.approved_at)
               OR (NEW.approved_at IS NOT NULL AND NEW.frozen_at IS NULL)
            THEN
                RAISE EXCEPTION 'requirements_versions rows are immutable';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER requirements_versions_no_update
            BEFORE UPDATE ON requirements_versions
            FOR EACH ROW EXECUTE FUNCTION requirements_versions_immutable();
        """
    )


def downgrade() -> None:
    # Refuse rather than silently delete discovery sessions the older schema cannot represent.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM runs WHERE agent_role = 'requirements-analyst') THEN
                RAISE EXCEPTION 'Downgrade refused: requirements analyst sessions exist. Export or delete them first.';
            END IF;
        END;
        $$;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS requirements_versions_no_update ON requirements_versions")
    op.execute("DROP FUNCTION IF EXISTS requirements_versions_immutable()")
    op.drop_index("uq_runs_one_active_per_project", table_name="runs", postgresql_where=sa.text(NEW_ACTIVE))
    op.create_index(
        "uq_runs_one_active_per_project", "runs", ["project_id"], unique=True, postgresql_where=sa.text(OLD_ACTIVE)
    )
    op.drop_constraint("ck_runs_agent_role", "runs", type_="check")
    op.drop_constraint("ck_runs_state", "runs", type_="check")
    op.create_check_constraint("ck_runs_state", "runs", OLD_STATES)
    op.drop_constraint("fk_runs_pinned_requirements_version", "runs", type_="foreignkey")
    op.drop_column("runs", "requirements_skipped")
    op.drop_column("runs", "pinned_requirements_version_id")
    op.drop_index("ix_requirements_versions_project_approved", table_name="requirements_versions")
    op.drop_table("requirements_versions")
    op.drop_index("ix_discovery_answers_question_created", table_name="discovery_answers")
    op.drop_table("discovery_answers")
    op.drop_table("discovery_questions")
    op.drop_index("ix_discovery_turns_created_by_created_at", table_name="discovery_turns")
    op.drop_index(
        "uq_discovery_turns_one_open_per_run",
        table_name="discovery_turns",
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.drop_table("discovery_turns")
