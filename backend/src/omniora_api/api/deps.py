from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request

from ..config import Settings
from ..db.models import User
from ..db.session import SessionFactory
from ..errors import ApiError
from ..services.auth import AuthService
from ..services.projects import ProjectsService
from ..services.requirements import RequirementsService
from ..services.runs import RunsService

SESSION_COOKIE = "omniora_session"


@dataclass(frozen=True)
class Container:
    settings: Settings
    factory: SessionFactory
    auth: AuthService
    projects: ProjectsService
    runs: RunsService
    requirements: RequirementsService


def get_container(request: Request) -> Container:
    return request.app.state.container


def current_user(request: Request, container: Container = Depends(get_container)) -> User:
    user = container.auth.user_for_token(request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise ApiError("unauthenticated", "Sign in to continue.")
    return user


def client_ip(request: Request) -> str:
    # Behind a reverse proxy, run uvicorn with --proxy-headers and trusted --forwarded-allow-ips.
    return request.client.host if request.client else "unknown"
