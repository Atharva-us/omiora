from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db.models import AuthSession, User


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(func.lower(User.email) == email.lower()))


def add_user(session: Session, *, email: str, name: str, password_hash: str, now: datetime) -> User:
    user = User(email=email, name=name, password_hash=password_hash, created_at=now)
    session.add(user)
    session.flush()
    return user


def add_session(session: Session, *, user_id: uuid.UUID, token_hash: str, now: datetime, expires_at: datetime) -> None:
    session.add(AuthSession(user_id=user_id, token_hash=token_hash, created_at=now, expires_at=expires_at))
    session.flush()


def get_user_for_session(session: Session, token_hash: str, now: datetime) -> User | None:
    return session.scalar(
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.token_hash == token_hash,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
    )


def revoke_session(session: Session, token_hash: str, now: datetime) -> None:
    session.execute(
        update(AuthSession)
        .where(AuthSession.token_hash == token_hash, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def set_password_hash(session: Session, user: User, password_hash: str) -> None:
    user.password_hash = password_hash
