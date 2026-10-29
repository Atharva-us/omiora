"""Password hashing (Argon2id) and opaque session tokens.

Session tokens are random 256-bit values given to the browser as an HttpOnly cookie. Only their
SHA-256 digest is stored, so a database leak does not expose usable sessions.
"""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()  # argon2-cffi defaults follow RFC 9106 recommendations (Argon2id)
# Verified against when the account does not exist, so response time does not reveal which emails exist.
_DUMMY_HASH = _hasher.hash("omniora-timing-equaliser")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_session_token() -> tuple[str, str]:
    """Returns (token for the cookie, digest for the database)."""
    token = secrets.token_urlsafe(32)
    return token, token_digest(token)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
