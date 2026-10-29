"""Migrations (on a separate scratch database), audit-log integrity, and health checks."""

from __future__ import annotations

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from omniora_api.audit import append_audit, verify_audit_chain
from omniora_api.db.models import AuditLog, Base
from omniora_api.db.session import transaction

from .conftest import alembic_config

SCRATCH_DB = "omniora_migration_check"


@pytest.fixture
def scratch_url(database_url: str):
    admin = create_engine(database_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH_DB}"))
        connection.execute(text(f"CREATE DATABASE {SCRATCH_DB}"))
    url = make_url(database_url).set(database=SCRATCH_DB).render_as_string(hide_password=False)
    yield url
    with admin.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH_DB} WITH (FORCE)"))
    admin.dispose()


def test_migrations_upgrade_downgrade_upgrade(scratch_url: str) -> None:
    config = alembic_config(scratch_url)
    command.upgrade(config, "head")
    engine = create_engine(scratch_url)
    assert "runs" in inspect(engine).get_table_names()
    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    command.upgrade(config, "head")
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert diff == [], f"ORM models and migrations differ: {diff}"


def test_audit_chain_detects_tampering(factory, engine) -> None:
    with transaction(factory) as session:
        for index in range(3):
            append_audit(
                session,
                actor_type="system",
                actor_id=None,
                action="test.event",
                entity_type="test",
                entity_id=str(index),
                data={"n": index},
            )
    with transaction(factory) as session:
        assert verify_audit_chain(session) is None

    # The database refuses edits outright...
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as connection:
        connection.execute(text("UPDATE audit_log SET data = '{\"n\": 99}' WHERE entity_id = '1'"))

    # ...and if storage is altered anyway (trigger bypassed by a superuser), the chain exposes it.
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_no_update_delete"))
        connection.execute(text("UPDATE audit_log SET data = '{\"n\": 99}' WHERE entity_id = '1'"))
        connection.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_no_update_delete"))
    with transaction(factory) as session:
        tampered_id = session.query(AuditLog.id).filter(AuditLog.entity_id == "1").scalar()
        assert verify_audit_chain(session) == tampered_id


def test_health_endpoints(client) -> None:
    assert client.get("/health/live").json() == {"status": "ok"}
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["checks"]["database"] == "ok" and ready.json()["checks"]["migrations"] == "ok"
    assert ready.json()["checks"]["model_provider"] == "not-configured"
