from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from ...db.session import transaction
from ..deps import Container, get_container

router = APIRouter(tags=["health"])


def _expected_revision() -> str | None:

    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[4] / "migrations"))
    return ScriptDirectory.from_config(config).get_current_head()


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def ready(container: Container = Depends(get_container)) -> JSONResponse:
    """Ready when the database answers and its schema is at the migration head."""
    checks: dict[str, str] = {}
    try:
        with transaction(container.factory) as session:
            session.execute(text("SELECT 1"))
            current = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        checks["database"] = "ok"
        checks["migrations"] = "ok" if current == _expected_revision() else "pending"
    except Exception:
        checks.setdefault("database", "unavailable")
        checks.setdefault("migrations", "unknown")
    checks["model_provider"] = "configured" if container.settings.model_configured else "not-configured"
    checks["model_provider_name"] = container.settings.model_provider
    ready_ = checks["database"] == "ok" and checks["migrations"] == "ok"
    return JSONResponse(
        {"status": "ready" if ready_ else "not-ready", "checks": checks}, status_code=200 if ready_ else 503
    )
