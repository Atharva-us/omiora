"""Application factory. Start the API with `uvicorn omniora_api.app:app` (see docs/BACKEND.md)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.deps import Container
from .api.middleware import BodySizeLimitMiddleware, CsrfMiddleware, SecurityHeadersMiddleware
from .api.routes import auth, health, projects, runs
from .config import Settings, get_settings
from .db.session import SessionFactory, make_engine, make_session_factory
from .errors import install_error_handlers
from .logging_setup import configure_logging
from .security.rate_limit import SlidingWindowLimiter
from .services import Clock, utcnow
from .services.auth import AuthService
from .services.projects import ProjectsService
from .services.runs import RunsService

API_PREFIX = "/api/v1"


def create_app(
    settings: Settings | None = None,
    *,
    factory: SessionFactory | None = None,
    provider_configured: bool | None = None,
    clock: Clock = utcnow,
) -> FastAPI:
    settings = settings or get_settings()
    if factory is None:
        configure_logging(settings.log_level)
        factory = make_session_factory(make_engine(settings.database_url))

    container = Container(
        settings=settings,
        factory=factory,
        auth=AuthService(
            factory,
            session_ttl_hours=settings.session_ttl_hours,
            signin_limiter=SlidingWindowLimiter(settings.signin_attempts_per_window, settings.signin_window_seconds),
            clock=clock,
        ),
        projects=ProjectsService(factory, clock),
        runs=RunsService(
            factory,
            runs_per_user_per_hour=settings.runs_per_user_per_hour,
            job_max_deliveries=settings.job_max_deliveries,
            provider_configured=settings.model_configured if provider_configured is None else provider_configured,
            clock=clock,
        ),
    )

    app = FastAPI(
        title="Omniora API",
        version="0.1.0",
        docs_url="/api/docs" if settings.env != "production" else None,
        openapi_url="/api/openapi.json" if settings.env != "production" else None,
        redoc_url=None,
    )
    app.state.container = container
    install_error_handlers(app)

    # Starlette applies middleware in reverse order of addition: the last added runs first.
    app.add_middleware(CsrfMiddleware, allowed_origins=settings.cors_origins)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Idempotency-Key", "Last-Event-ID", "X-Omniora-Client"],
        max_age=600,
    )
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.env == "production")

    app.include_router(health.router)
    for router in (auth.router, projects.router, runs.router):
        app.include_router(router, prefix=API_PREFIX)
    return app


def __getattr__(name: str) -> FastAPI:
    # `uvicorn omniora_api.app:app` builds the app lazily so importing this module has no side effects.
    if name == "app":
        return create_app()
    raise AttributeError(name)
