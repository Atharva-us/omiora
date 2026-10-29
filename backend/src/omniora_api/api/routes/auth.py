from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from ...errors import ApiError
from ..deps import SESSION_COOKIE, Container, client_ip, current_user, get_container
from ..mappers import user_out
from ..schemas import AuthUserOut, PasswordResetIn, RegisterIn, SignInIn

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, container: Container, token: str, max_age: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=bool(container.settings.cookie_secure),
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=AuthUserOut, status_code=201)
def register(body: RegisterIn, response: Response, container: Container = Depends(get_container)) -> AuthUserOut:
    signed_in = container.auth.register(email=body.email, name=body.name, password=body.password)
    _set_session_cookie(response, container, signed_in.token, signed_in.max_age_seconds)
    return user_out(signed_in.user)


@router.post("/sign-in", response_model=AuthUserOut)
def sign_in(
    body: SignInIn, request: Request, response: Response, container: Container = Depends(get_container)
) -> AuthUserOut:
    signed_in = container.auth.sign_in(email=body.email, password=body.password, client_ip=client_ip(request))
    _set_session_cookie(response, container, signed_in.token, signed_in.max_age_seconds)
    return user_out(signed_in.user)


@router.post("/sign-out", status_code=204)
def sign_out(request: Request, response: Response, container: Container = Depends(get_container)) -> Response:
    container.auth.sign_out(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(
        SESSION_COOKIE, path="/", httponly=True, secure=bool(container.settings.cookie_secure), samesite="lax"
    )
    response.status_code = 204
    return response


@router.get("/me", response_model=AuthUserOut)
def me(user=Depends(current_user)) -> AuthUserOut:
    return user_out(user)


@router.post("/password-reset", status_code=202)
def password_reset(_: PasswordResetIn) -> None:
    # Honest failure: there is no email delivery, so no reset message can be sent.
    raise ApiError(
        "provider-not-configured", "Password reset is not available yet because email delivery is not configured."
    )
