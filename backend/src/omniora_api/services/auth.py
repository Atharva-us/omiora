"""Email and password accounts with server-side sessions.

This is a real, verifiable identity mechanism: passwords are Argon2id-hashed, sessions are random
tokens held in HttpOnly cookies and checked against the database on every request, and sign-out
revokes the session server-side. Not yet implemented, and required before a public launch: email
verification, password reset delivery, and MFA (see docs/BACKEND.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta

from ..audit import append_audit
from ..db.models import User
from ..db.session import SessionFactory, transaction
from ..errors import ApiError
from ..repositories import users as users_repo
from ..security.credentials import hash_password, needs_rehash, new_session_token, token_digest, verify_password
from ..security.rate_limit import SlidingWindowLimiter
from . import Clock, utcnow

EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_MIN = 8
PASSWORD_MAX = 256


@dataclass(frozen=True)
class SignedIn:
    user: User
    token: str
    max_age_seconds: int


class AuthService:
    def __init__(
        self,
        factory: SessionFactory,
        *,
        session_ttl_hours: int,
        signin_limiter: SlidingWindowLimiter,
        clock: Clock = utcnow,
    ) -> None:
        self._factory = factory
        self._ttl = timedelta(hours=session_ttl_hours)
        self._limiter = signin_limiter
        self._clock = clock

    def _start_session(self, session, user: User) -> SignedIn:
        now = self._clock()
        token, digest = new_session_token()
        users_repo.add_session(session, user_id=user.id, token_hash=digest, now=now, expires_at=now + self._ttl)
        return SignedIn(user=user, token=token, max_age_seconds=int(self._ttl.total_seconds()))

    def register(self, *, email: str, name: str, password: str) -> SignedIn:
        email = email.strip()
        name = name.strip()
        problems = []
        if not EMAIL.match(email) or len(email) > 320:
            problems.append("Enter a valid email address.")
        if not name or len(name) > 100:
            problems.append("Enter your name (up to 100 characters).")
        if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
            problems.append(f"Use a password of {PASSWORD_MIN} to {PASSWORD_MAX} characters.")
        if problems:
            raise ApiError("validation", "The account details are not valid.", details=problems)
        with transaction(self._factory) as session:
            if users_repo.get_user_by_email(session, email):
                raise ApiError("email-in-use", "An account with this email already exists.")
            user = users_repo.add_user(
                session, email=email, name=name, password_hash=hash_password(password), now=self._clock()
            )
            append_audit(
                session,
                actor_type="user",
                actor_id=str(user.id),
                action="user.registered",
                entity_type="user",
                entity_id=str(user.id),
            )
            return self._start_session(session, user)

    def sign_in(self, *, email: str, password: str, client_ip: str) -> SignedIn:
        email = email.strip().lower()
        retry_after = self._limiter.hit(f"{client_ip}|{email}")
        if retry_after is not None:
            raise ApiError(
                "rate-limited",
                "Too many sign-in attempts. Try again later.",
                headers={"Retry-After": str(int(retry_after) + 1)},
            )
        with transaction(self._factory) as session:
            user = users_repo.get_user_by_email(session, email)
            if not verify_password(user.password_hash if user else None, password) or user is None:
                raise ApiError("invalid-credentials", "The email or password is incorrect.")
            if needs_rehash(user.password_hash):
                users_repo.set_password_hash(session, user, hash_password(password))
            self._limiter.reset(f"{client_ip}|{email}")
            append_audit(
                session,
                actor_type="user",
                actor_id=str(user.id),
                action="user.signed-in",
                entity_type="user",
                entity_id=str(user.id),
            )
            return self._start_session(session, user)

    def user_for_token(self, token: str | None) -> User | None:
        if not token or len(token) > 200:
            return None
        with transaction(self._factory) as session:
            return users_repo.get_user_for_session(session, token_digest(token), self._clock())

    def sign_out(self, token: str | None) -> None:
        if not token or len(token) > 200:
            return
        with transaction(self._factory) as session:
            users_repo.revoke_session(session, token_digest(token), self._clock())
