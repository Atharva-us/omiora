from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from omniora_api.db.models import AuthSession, User

from .conftest import ORIGIN

REGISTER = {"name": "Ada", "email": "Ada@Example.com", "password": "correct horse"}


def test_register_sign_in_me_and_sign_out(client: TestClient, make_client, factory) -> None:
    response = client.post("/api/v1/auth/register", json=REGISTER)
    assert response.status_code == 201
    assert response.json()["email"] == "Ada@Example.com"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
    assert client.get("/api/v1/auth/me").json()["name"] == "Ada"

    with factory() as session:
        user = session.scalar(select(User))
        stored = session.scalar(select(AuthSession))
    assert user.password_hash.startswith("$argon2id$")  # never the plaintext
    assert client.cookies.get("omniora_session") != stored.token_hash  # only a digest is stored

    other = make_client()
    signed = other.post("/api/v1/auth/sign-in", json={"email": "ada@example.com", "password": "correct horse"})
    assert signed.status_code == 200

    assert client.post("/api/v1/auth/sign-out").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    assert other.get("/api/v1/auth/me").status_code == 200  # other sessions are unaffected


def test_revoked_cookie_cannot_be_replayed(client: TestClient, make_client) -> None:
    client.post("/api/v1/auth/register", json=REGISTER)
    token = client.cookies.get("omniora_session")
    client.post("/api/v1/auth/sign-out")
    replay = make_client()
    replay.cookies.set("omniora_session", token)
    assert replay.get("/api/v1/auth/me").json()["error"]["code"] == "unauthenticated"


def test_session_expiry(client: TestClient, clock) -> None:
    client.post("/api/v1/auth/register", json=REGISTER)
    clock.advance(15 * 24 * 3600)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_rejects_bad_credentials_and_duplicates(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=REGISTER)
    assert client.post("/api/v1/auth/register", json=REGISTER).json()["error"]["code"] == "email-in-use"
    wrong = client.post("/api/v1/auth/sign-in", json={"email": "ada@example.com", "password": "nope nope"})
    assert wrong.status_code == 401 and wrong.json()["error"]["code"] == "invalid-credentials"
    unknown = client.post("/api/v1/auth/sign-in", json={"email": "who@example.com", "password": "whatever1"})
    assert unknown.json()["error"]["message"] == wrong.json()["error"]["message"]  # no account enumeration here


def test_registration_validation(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={"name": "", "email": "nope", "password": "short"})
    assert response.status_code == 422
    assert len(response.json()["error"]["details"]) == 3
    assert "short" not in response.text  # submitted values are never echoed


def test_sign_in_is_rate_limited(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=REGISTER)
    for _ in range(10):
        client.post("/api/v1/auth/sign-in", json={"email": "ada@example.com", "password": "wrong-password"})
    limited = client.post("/api/v1/auth/sign-in", json={"email": "ada@example.com", "password": "correct horse"})
    assert limited.status_code == 429 and "Retry-After" in limited.headers


def test_csrf_header_and_origin_are_enforced(app) -> None:
    bare = TestClient(app)
    assert bare.post("/api/v1/auth/register", json=REGISTER).json()["error"]["code"] == "forbidden"
    evil = TestClient(app, headers={"X-Omniora-Client": "web", "Origin": "https://evil.example"})
    assert evil.post("/api/v1/auth/register", json=REGISTER).status_code == 403
    good = TestClient(app, headers={"X-Omniora-Client": "web", "Origin": ORIGIN})
    assert good.post("/api/v1/auth/register", json=REGISTER).status_code == 201


def test_cors_preflight(app) -> None:
    client = TestClient(app)
    allowed = client.options(
        "/api/v1/projects",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-omniora-client",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    assert allowed.headers["access-control-allow-credentials"] == "true"
    denied = client.options(
        "/api/v1/projects", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    )
    assert "access-control-allow-origin" not in denied.headers


def test_password_reset_is_honestly_unavailable(client: TestClient) -> None:
    response = client.post("/api/v1/auth/password-reset", json={"email": "ada@example.com"})
    assert response.status_code == 503 and response.json()["error"]["code"] == "provider-not-configured"


def test_security_headers(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
