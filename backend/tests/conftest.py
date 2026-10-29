"""Fixtures. Database tests run against the real PostgreSQL named by OMNIORA_TEST_DATABASE_URL;
they are skipped (and reported as skipped) when it is not set. They never fall back to SQLite."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from omniora_api.app import create_app
from omniora_api.config import Settings
from omniora_api.db.session import SessionFactory, make_session_factory
from omniora_api.worker.planning import PlanningJobHandler
from omniora_api.worker.runner import Worker

from .support import FakeClock, ScriptedProvider

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGIN = "http://localhost:5173"


def _psycopg_url(url: str) -> str:
    return "postgresql+psycopg://" + url.removeprefix("postgresql://") if url.startswith("postgresql://") else url


def alembic_config(url: str) -> Config:
    config = Config(os.path.join(BACKEND_ROOT, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(BACKEND_ROOT, "migrations"))
    config.attributes["url"] = url
    return config


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("OMNIORA_TEST_DATABASE_URL")
    if not url:
        pytest.skip("OMNIORA_TEST_DATABASE_URL is not set; database tests need a real PostgreSQL instance")
    return _psycopg_url(url)


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    command.upgrade(alembic_config(database_url), "head")
    yield engine
    engine.dispose()


@pytest.fixture
def factory(engine: Engine) -> Iterator[SessionFactory]:
    yield make_session_factory(engine)
    with engine.begin() as connection:
        tables = connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'")
        ).scalars()
        connection.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,  # never read a developer's .env during tests
        env="test",
        database_url=database_url,
        cors_origins=[ORIGIN],
        sse_poll_seconds=0.01,
        sse_heartbeat_seconds=0.05,
        sse_max_stream_seconds=2,
    )


@pytest.fixture
def app(settings: Settings, factory: SessionFactory, clock: FakeClock):
    return create_app(settings, factory=factory, provider_configured=True, clock=clock)


@pytest.fixture
def make_client(app) -> Callable[[], TestClient]:
    """Each client has its own cookie jar, i.e. its own browser session."""

    def build() -> TestClient:
        return TestClient(app, headers={"X-Omniora-Client": "web", "Origin": ORIGIN})

    return build


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


@pytest.fixture
def signed_in(make_client) -> Callable[[str], TestClient]:
    def build(email: str = "ada@example.com") -> TestClient:
        c = make_client()
        response = c.post("/api/v1/auth/register", json={"name": "Ada", "email": email, "password": "correct horse"})
        assert response.status_code == 201, response.text
        return c

    return build


@pytest.fixture
def make_worker(factory: SessionFactory, settings: Settings, clock: FakeClock) -> Callable[..., Worker]:
    def build(provider: ScriptedProvider, owner: str = "worker-a", **setting_overrides) -> Worker:
        worker_settings = settings.model_copy(update=setting_overrides)
        handler = PlanningJobHandler(factory, provider, worker_settings, clock)
        return Worker(factory, handler, owner=owner, lease_seconds=60, clock=clock)

    return build
