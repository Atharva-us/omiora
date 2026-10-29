"""Projects API. Mirrors the behaviours in src/test/contracts/project-service.contract.ts."""

from __future__ import annotations

import uuid

from .support import configuration

API = "/api/v1/projects"


def test_requires_authentication(client) -> None:
    response = client.get(API)
    assert response.status_code == 401 and response.json()["error"]["code"] == "unauthenticated"


def test_create_returns_server_generated_uuid7_and_configured_status(signed_in) -> None:
    client = signed_in()
    response = client.post(
        API, json=configuration(name="  Spaced  ", stack={"mode": "custom", "technologies": ["react", "react"]})
    )
    assert response.status_code == 201
    body = response.json()
    assert uuid.UUID(body["id"]).version == 7
    assert body["source"] == "user" and body["status"] == "configured"
    assert body["configuration"]["name"] == "Spaced"
    assert body["configuration"]["stack"] == {"mode": "custom", "technologies": ["react"]}
    assert body["createdAt"].endswith("Z")
    assert client.get(f"{API}/{body['id']}").json() == body


def test_enforces_the_same_rules_as_the_frontend(signed_in) -> None:
    client = signed_in()
    response = client.post(API, json=configuration(stack={"mode": "custom", "technologies": ["react", "nextjs"]}))
    assert response.status_code == 422
    assert any("React and Next.js" in detail for detail in response.json()["error"]["details"])
    assert client.post(API, json=configuration(referenceUrl="javascript:alert(1)")).status_code == 422
    project = client.post(API, json=configuration()).json()
    assert client.patch(f"{API}/{project['id']}", json={"name": "x" * 81}).status_code == 422
    assert client.post(f"{API}/{project['id']}/notes", json={"content": "y" * 1001}).status_code == 422
    assert client.post(f"{API}/{project['id']}/notes", json={"content": "   "}).status_code == 422
    assert client.post(API, json={**configuration(), "ownerId": "someone"}).status_code == 422


def test_update_history_notes_and_delete(signed_in, clock) -> None:
    client = signed_in()
    project = client.post(API, json=configuration()).json()
    clock.advance(1)
    renamed = client.patch(f"{API}/{project['id']}", json={"name": "Renamed"}).json()
    assert renamed["configuration"]["name"] == "Renamed" and renamed["updatedAt"] > project["updatedAt"]
    client.patch(
        f"{API}/{project['id']}",
        json={
            "configuration": configuration(
                name="Renamed", platform="mobile", stack={"mode": "custom", "technologies": ["flutter"]}
            )
        },
    )
    client.post(f"{API}/{project['id']}/notes", json={"content": "First"})
    client.post(f"{API}/{project['id']}/notes", json={"content": "Second"})

    history = [entry["summary"] for entry in client.get(f"{API}/{project['id']}/history").json()]
    assert history == [
        "Requirement note added.",
        "Requirement note added.",
        "Configuration updated.",
        'Renamed to "Renamed".',
        "Project created from the configuration wizard.",
    ]
    assert [n["content"] for n in client.get(f"{API}/{project['id']}/notes").json()] == ["First", "Second"]

    assert client.delete(f"{API}/{project['id']}").status_code == 204
    assert client.get(f"{API}/{project['id']}").status_code == 404


def test_samples_are_public_and_read_only(client, signed_in) -> None:
    samples = client.get(f"{API}/samples").json()
    assert len(samples) == 3 and all(s["source"] == "sample" for s in samples)
    user = signed_in()
    sample_id = samples[0]["id"]
    assert user.get(f"{API}/{sample_id}").json()["id"] == sample_id
    assert user.patch(f"{API}/{sample_id}", json={"name": "Mine"}).json()["error"]["code"] == "read-only"
    assert user.delete(f"{API}/{sample_id}").status_code == 403
    assert user.post(f"{API}/{sample_id}/notes", json={"content": "x"}).status_code == 403
    assert user.get(f"{API}/{sample_id}/history").json() == []


def test_projects_are_isolated_between_users(signed_in) -> None:
    owner = signed_in("owner@example.com")
    intruder = signed_in("intruder@example.com")
    project = owner.post(API, json=configuration()).json()
    for response in (
        intruder.get(f"{API}/{project['id']}"),
        intruder.patch(f"{API}/{project['id']}", json={"name": "Taken"}),
        intruder.delete(f"{API}/{project['id']}"),
        intruder.get(f"{API}/{project['id']}/notes"),
    ):
        assert response.status_code == 404  # existence is not disclosed
    assert intruder.get(API).json()["items"] == []
    assert owner.get(f"{API}/{project['id']}").status_code == 200


def test_keyset_pagination_is_ordered_and_complete(signed_in, clock) -> None:
    client = signed_in()
    created = []
    for index in range(5):
        created.append(client.post(API, json=configuration(name=f"Project {index}")).json()["id"])
        if index % 2:
            clock.advance(1)  # some share a timestamp: the id breaks ties
    first = client.get(API, params={"limit": 2}).json()
    assert len(first["items"]) == 2 and first["nextCursor"]
    seen = [p["id"] for p in first["items"]]
    cursor = first["nextCursor"]
    while cursor:
        page = client.get(API, params={"limit": 2, "cursor": cursor}).json()
        seen += [p["id"] for p in page["items"]]
        cursor = page["nextCursor"]
    assert seen == list(reversed(created))
    assert client.get(API, params={"cursor": "garbage!"}).status_code == 422


def test_unknown_and_malformed_ids_are_not_found(signed_in) -> None:
    client = signed_in()
    assert client.get(f"{API}/{uuid.uuid4()}").status_code == 404
    assert client.get(f"{API}/prj_local_demo_id").status_code == 404


def test_body_size_limit(signed_in) -> None:
    client = signed_in()
    response = client.post(API, content=b"{" + b" " * 70_000 + b"}", headers={"Content-Type": "application/json"})
    assert response.status_code == 413
