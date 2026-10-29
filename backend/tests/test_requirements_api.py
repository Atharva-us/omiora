"""Requirements Analyst sessions against real PostgreSQL: discovery turns, answers, idempotency,
concurrency, worker recovery, approval, version immutability, authorization, and the handoff
that pins approved requirements to a planning run. The model is always a ScriptedProvider."""

from __future__ import annotations

import threading
import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from omniora_api.audit import verify_audit_chain
from omniora_api.db.models import DiscoveryAnswer, DiscoveryQuestion, DiscoveryTurn, Job, RequirementsVersion
from omniora_api.errors import ApiError
from omniora_api.services.requirements import AnswerInput

from .support import (
    ScriptedProvider,
    analyst_context,
    analyst_json,
    configuration,
    model_error,
    plan_json,
    question,
    requirement_op,
)

PROJECTS = "/api/v1/projects"
SESSIONS = "/api/v1/requirements-sessions"

# Turn 2 after DQ-001 was answered: a requirement backed by that answer, and readiness.
READY_TURN = analyst_json(
    operations=[
        requirement_op(statement="Checkout accepts card payments.", source="answer", evidence=["answer:DQ-001"])
    ],
    questions=[],
    readiness={"ready": True, "blockers": []},
)


def create_project(client, **overrides) -> str:
    return client.post(PROJECTS, json=configuration(**overrides)).json()["id"]


def start_session(client, project_id: str, key: str = "session-key-0001"):
    return client.post(f"{PROJECTS}/{project_id}/requirements-sessions", headers={"Idempotency-Key": key})


def detail(client, session_id: str) -> dict:
    response = client.get(f"{SESSIONS}/{session_id}")
    assert response.status_code == 200, response.text
    return response.json()


def answer(client, session_id: str, answers: list[dict], *, advance: bool = True, key: str | None = None):
    return client.post(
        f"{SESSIONS}/{session_id}/answers",
        headers={"Idempotency-Key": key or f"answers-{uuid.uuid4().hex[:12]}"},
        json={"answers": answers, "advance": advance},
    )


def submit(client, session_id: str, version: int):
    return client.post(f"{SESSIONS}/{session_id}/submit", json={"version": version})


def decide(client, session_id: str, decision: str, version: int, comment: str | None = None):
    approval_id = detail(client, session_id)["approvals"][-1]["id"]
    return client.post(
        f"{SESSIONS}/{session_id}/approvals/{approval_id}",
        json={"decision": decision, "version": version, "comment": comment},
    )


def event_types(client, session_id: str) -> list[str]:
    return [e["type"] for e in client.get(f"/api/v1/runs/{session_id}/events/history").json()]


def discovered(signed_in, make_worker, *turn_outputs: str):
    """A session whose first turn has run (asking DQ-001)."""
    client = signed_in()
    project_id = create_project(client)
    session_id = start_session(client, project_id).json()["id"]
    assert make_worker(ScriptedProvider(*(turn_outputs or (analyst_json(),)))).run_once()
    return client, project_id, session_id


def approved_session(signed_in, make_worker):
    client, project_id, session_id = discovered(signed_in, make_worker)
    assert answer(client, session_id, [{"questionKey": "DQ-001", "value": ["Cards"]}]).status_code == 200
    assert make_worker(ScriptedProvider(READY_TURN)).run_once()
    assert submit(client, session_id, 2).status_code == 200
    assert decide(client, session_id, "approve", 2).status_code == 200
    return client, project_id, session_id


def pinned_plan_json() -> str:
    return plan_json(
        requirements=[],
        tasks=[
            {
                "key": "T1",
                "title": "Catalogue",
                "description": "Category pages.",
                "acceptance_criteria": ["Products render by category"],
                "depends_on": [],
                "requirement_ids": ["REQ-001"],
                "suggested_agent": "frontend-engineer",
            },
            {
                "key": "T2",
                "title": "Card checkout",
                "description": "Hosted card payment.",
                "acceptance_criteria": ["A test card payment succeeds"],
                "depends_on": ["T1"],
                "requirement_ids": ["REQ-002"],
                "suggested_agent": "backend-engineer",
            },
        ],
    )


class TestDiscoveryFlow:
    def test_start_is_idempotent_and_runs_the_first_turn(self, signed_in, make_worker, settings) -> None:
        client = signed_in()
        project_id = create_project(client)
        first = start_session(client, project_id)
        assert first.status_code == 202 and first.json()["state"] == "queued"
        repeat = start_session(client, project_id)
        assert repeat.status_code == 200 and repeat.json()["id"] == first.json()["id"]
        session_id = first.json()["id"]
        assert detail(client, session_id)["turn"]["status"] == "queued"  # the UI shows "analysing" from this

        provider = ScriptedProvider(analyst_json())
        assert make_worker(provider).run_once()
        body = detail(client, session_id)
        assert body["session"]["state"] == "discovering" and body["turn"]["status"] == "completed"
        assert [q["key"] for q in body["questions"]] == ["DQ-001"] and body["questions"][0]["answer"] is None
        assert body["version"]["version"] == 1 and body["version"]["content"]["requirements"][0]["id"] == "REQ-001"
        assert body["version"]["ready"] is False and body["version"]["content"]["readiness"]["blockers"]
        assert "<project_brief>" in provider.requests[0].user_content
        assert provider.requests[0].max_output_tokens == settings.analyst_output_tokens

    def test_full_lifecycle_to_a_pinned_plan(self, signed_in, make_worker, factory) -> None:
        client, project_id, session_id = discovered(signed_in, make_worker)
        saved = answer(client, session_id, [{"questionKey": "DQ-001", "value": ["Cards", "PayPal"]}])
        assert saved.status_code == 200 and saved.json()["turn"]["number"] == 2
        assert saved.json()["questions"][0]["answer"]["value"] == ["Cards", "PayPal"]

        provider = ScriptedProvider(READY_TURN)
        assert make_worker(provider).run_once()
        assert '"answer":["Cards","PayPal"]' in provider.requests[0].user_content  # compact authoritative summary
        body = detail(client, session_id)
        assert body["session"]["state"] == "ready-for-review" and body["version"]["ready"] is True
        ids = [r["id"] for r in body["version"]["content"]["requirements"]]
        assert ids == ["REQ-001", "REQ-002"]

        submitted = submit(client, session_id, 2)
        assert submitted.status_code == 200 and submitted.json()["session"]["state"] == "awaiting-approval"
        assert submitted.json()["version"]["frozenAt"] is not None
        assert submit(client, session_id, 2).status_code == 200  # idempotent
        approved = decide(client, session_id, "approve", 2)
        assert approved.json()["session"]["state"] == "approved"
        assert approved.json()["version"]["approvedAt"] is not None

        handoff = client.get(f"{PROJECTS}/{project_id}/requirements/approved").json()
        assert handoff["sessionId"] == session_id and handoff["version"]["version"] == 2
        sha = handoff["version"]["contentSha256"]

        run = client.post(f"{PROJECTS}/{project_id}/runs", headers={"Idempotency-Key": "plan-key-0001"})
        assert run.status_code == 202, run.text
        assert run.json()["pinnedRequirementsVersionId"] == handoff["version"]["id"]
        assert run.json()["requirementsSkipped"] is False
        planner = ScriptedProvider(pinned_plan_json())
        assert make_worker(planner).run_once()
        content = planner.requests[0].user_content
        assert f'sha256="{sha}"' in content and '"id": "REQ-002"' in content
        run_detail = client.get(f"/api/v1/runs/{run.json()['id']}").json()
        assert run_detail["run"]["state"] == "awaiting-approval"
        assert run_detail["requirements"] == {
            "versionId": handoff["version"]["id"],
            "sessionId": session_id,
            "version": 2,
            "contentSha256": sha,
        }
        assert [t["requirementIds"] for t in run_detail["tasks"]] == [["REQ-001"], ["REQ-002"]]

        assert event_types(client, session_id) == [
            "run.created",
            "turn.queued",
            "run.state-changed",
            "attempt.started",
            "attempt.finished",
            "requirements.version-created",
            "turn.completed",
            "answers.submitted",
            "turn.queued",
            "attempt.started",
            "attempt.finished",
            "requirements.version-created",
            "turn.completed",
            "run.state-changed",
            "approval.requested",
            "run.state-changed",
            "approval.decided",
            "run.state-changed",
        ]
        with factory() as session:
            assert verify_audit_chain(session) is None
            actions = list(session.execute(text("SELECT action FROM audit_log ORDER BY id")).scalars())
        for action in (
            "requirements.session-started",
            "requirements.answers-submitted",
            "requirements.version-created",
            "requirements.submitted",
            "requirements.approved",
            "run.started",
        ):
            assert action in actions

    def test_plan_that_misses_an_approved_must_have_is_retried(self, signed_in, make_worker) -> None:
        client, project_id, _ = approved_session(signed_in, make_worker)
        run_id = client.post(f"{PROJECTS}/{project_id}/runs", headers={"Idempotency-Key": "plan-key-0002"}).json()["id"]
        incomplete = plan_json(
            requirements=[],
            tasks=[
                {
                    "key": "T1",
                    "title": "Catalogue",
                    "description": "Pages.",
                    "acceptance_criteria": ["Renders"],
                    "depends_on": [],
                    "requirement_ids": ["REQ-001"],
                    "suggested_agent": "frontend-engineer",
                }
            ],
        )
        assert make_worker(ScriptedProvider(incomplete, pinned_plan_json())).run_once()
        attempts = client.get(f"/api/v1/runs/{run_id}").json()["attempts"]
        assert [a["outcome"] for a in attempts] == ["invalid-output", "succeeded"]
        assert any("'REQ-002' is neither covered" in p for p in attempts[0]["validationErrors"])

    def test_planning_needs_approved_requirements_or_an_explicit_skip(self, signed_in) -> None:
        client = signed_in()
        project_id = create_project(client)
        blocked = client.post(f"{PROJECTS}/{project_id}/runs", headers={"Idempotency-Key": "plan-key-0003"})
        assert blocked.status_code == 409 and "Requirements Analyst" in blocked.json()["error"]["message"]
        skipped = client.post(
            f"{PROJECTS}/{project_id}/runs",
            headers={"Idempotency-Key": "plan-key-0004"},
            json={"withoutRequirements": True},
        )
        assert skipped.status_code == 202
        assert skipped.json()["requirementsSkipped"] is True and skipped.json()["pinnedRequirementsVersionId"] is None

    def test_one_active_run_per_project_across_roles(self, signed_in, make_worker) -> None:
        client, project_id, _ = discovered(signed_in, make_worker)
        conflict = client.post(
            f"{PROJECTS}/{project_id}/runs",
            headers={"Idempotency-Key": "plan-key-0005"},
            json={"withoutRequirements": True},
        )
        assert conflict.status_code == 409
        assert start_session(client, project_id, key="session-key-0002").status_code == 409

    def test_planning_list_and_plan_routes_ignore_requirements_sessions(self, signed_in, make_worker) -> None:
        client, project_id, session_id = discovered(signed_in, make_worker)
        assert client.get(f"{PROJECTS}/{project_id}/runs").json() == []
        assert [s["id"] for s in client.get(f"{PROJECTS}/{project_id}/requirements-sessions").json()] == [session_id]
        assert client.post(f"/api/v1/runs/{session_id}/cancel").status_code == 409


class TestAnswers:
    def test_answer_types_are_validated(self, signed_in, make_worker) -> None:
        client, _, session_id = discovered(
            signed_in,
            make_worker,
            analyst_json(
                questions=[
                    question(),
                    question(prompt="Is there a launch deadline?", kind="yes-no", options=[], blocking=False),
                    question(prompt="Describe the brand voice.", kind="free-text", options=[], blocking=False),
                ]
            ),
        )
        cases = [
            ({"questionKey": "DQ-001", "value": ["Crypto"]}, 422),
            ({"questionKey": "DQ-001", "value": []}, 422),
            ({"questionKey": "DQ-002", "value": "yes"}, 422),
            ({"questionKey": "DQ-003", "value": "   "}, 422),
            ({"questionKey": "DQ-003", "value": "x" * 2001}, 422),
            ({"questionKey": "DQ-001", "unknown": True, "value": ["Cards"]}, 422),
            ({"questionKey": "DQ-999", "value": "x"}, 404),
            ({"questionKey": "Q1", "value": "x"}, 422),
        ]
        for body, status in cases:
            assert answer(client, session_id, [body], advance=False).status_code == status, body
        duplicate = answer(client, session_id, [{"questionKey": "DQ-002", "value": True}] * 2, advance=False)
        assert duplicate.status_code == 422
        assert answer(client, session_id, [], advance=False).status_code == 422
        too_many = answer(client, session_id, [{"questionKey": "DQ-002", "value": True}] * 21, advance=False)
        assert too_many.status_code == 422

    def test_answers_are_editable_and_append_only(self, signed_in, make_worker, factory) -> None:
        client, _, session_id = discovered(signed_in, make_worker)
        assert (
            answer(client, session_id, [{"questionKey": "DQ-001", "value": ["Cards"]}], advance=False).status_code
            == 200
        )
        edited = answer(client, session_id, [{"questionKey": "DQ-001", "value": ["PayPal"]}], advance=False)
        assert edited.json()["questions"][0]["answer"]["value"] == ["PayPal"]
        assert edited.json()["turn"]["number"] == 1  # saved as a draft: no new turn
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(DiscoveryAnswer)) == 2  # history kept

    def test_replayed_submission_is_applied_once(self, signed_in, make_worker, factory) -> None:
        client, _, session_id = discovered(signed_in, make_worker)
        body = [{"questionKey": "DQ-001", "value": ["Cards"]}]
        first = answer(client, session_id, body, key="answers-retry-01")
        again = answer(client, session_id, body, key="answers-retry-01")
        assert first.status_code == again.status_code == 200
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(DiscoveryAnswer)) == 1
            assert session.scalar(select(func.count()).select_from(DiscoveryTurn)) == 2
            assert session.scalar(select(func.count()).select_from(Job)) == 2

    def test_answers_wait_while_the_analyst_is_working(self, signed_in, make_worker) -> None:
        client, _, session_id = discovered(signed_in, make_worker)
        assert answer(client, session_id, [{"questionKey": "DQ-001", "value": ["Cards"]}]).status_code == 200
        busy = answer(client, session_id, [{"questionKey": "DQ-001", "value": ["PayPal"]}], advance=False)
        assert busy.status_code == 409 and "still working" in busy.json()["error"]["message"]

    def test_concurrent_submissions_cannot_advance_the_same_turn_twice(
        self, signed_in, make_worker, app, factory
    ) -> None:
        client, _, session_id = discovered(signed_in, make_worker)
        user_id = uuid.UUID(client.get("/api/v1/auth/me").json()["id"])
        service = app.state.container.requirements
        barrier = threading.Barrier(2)
        outcomes: list[str] = []

        def submit_concurrently(key: str) -> None:
            barrier.wait()
            try:
                service.answer(user_id, uuid.UUID(session_id), key, [AnswerInput("DQ-001", ["Cards"])], advance=True)
                outcomes.append("ok")
            except ApiError as error:
                outcomes.append(error.code)

        threads = [threading.Thread(target=submit_concurrently, args=(f"concurrent-{n:04d}",)) for n in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert sorted(outcomes) == ["conflict", "ok"]
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(DiscoveryTurn)) == 2
            assert session.scalar(select(func.count()).select_from(Job).where(Job.status == "queued")) == 1

    def test_changing_an_answer_after_readiness_reopens_discovery(self, signed_in, make_worker) -> None:
        client, _, session_id = discovered(signed_in, make_worker)
        answer(client, session_id, [{"questionKey": "DQ-001", "value": ["Cards"]}])
        make_worker(ScriptedProvider(READY_TURN)).run_once()
        reopened = answer(client, session_id, [{"questionKey": "DQ-001", "value": ["PayPal"]}], advance=False)
        assert reopened.json()["session"]["state"] == "discovering" and reopened.json()["turn"]["status"] == "queued"
        assert submit(client, session_id, 2).status_code == 409  # the stale version cannot be submitted

    def test_turn_limit(self, signed_in, make_worker, settings, app, factory, clock) -> None:
        app.state.container.requirements._max_turns = 1
        client, _, session_id = discovered(signed_in, make_worker)
        limited = answer(client, session_id, [{"questionKey": "DQ-001", "value": ["Cards"]}])
        assert limited.status_code == 409 and "discovery turns" in limited.json()["error"]["message"]


class TestAnalystOutputs:
    def test_i_dont_know_needs_a_qualified_assumption_before_readiness(self, signed_in, make_worker) -> None:
        client, _, session_id = discovered(signed_in, make_worker)
        saved = answer(client, session_id, [{"questionKey": "DQ-001", "unknown": True}])
        assert saved.json()["questions"][0]["answer"] == {
            "value": None,
            "unknown": True,
            "answeredAt": saved.json()["questions"][0]["answer"]["answeredAt"],
        }
        claims_fact = analyst_json(
            operations=[requirement_op(statement="Cards only.", source="answer", evidence=["answer:DQ-001"])],
            questions=[],
            readiness={"ready": True, "blockers": []},
        )
        bare_ready = analyst_json(operations=[], questions=[], readiness={"ready": True, "blockers": []})
        qualified = analyst_json(
            operations=[],
            questions=[],
            assumptions=[{"statement": "Start with card payments.", "confidence": "low", "basis": ["DQ-001"]}],
            readiness={"ready": True, "blockers": []},
        )
        provider = ScriptedProvider(claims_fact, bare_ready, qualified)
        assert make_worker(provider).run_once()
        assert "I don't know" in provider.requests[0].user_content
        body = detail(client, session_id)
        assert [a["outcome"] for a in body["attempts"] if a["turn"] == 2] == [
            "invalid-output",
            "invalid-output",
            "succeeded",
        ]
        assert body["session"]["state"] == "ready-for-review"
        assert body["version"]["content"]["openQuestions"][0]["status"] == "unknown"
        assert body["version"]["content"]["assumptions"][0]["confidence"] == "low"

    def test_invented_answers_exhaust_the_turn_but_keep_answers_and_allow_retry(self, signed_in, make_worker) -> None:
        client, _, session_id = discovered(signed_in, make_worker)
        answer(client, session_id, [{"questionKey": "DQ-001", "value": ["Cards"]}])
        invented = analyst_json(
            operations=[requirement_op(source="answer", evidence=["answer:DQ-002"])],  # DQ-002 was never asked
            questions=[],
        )
        assert make_worker(ScriptedProvider(invented, invented, invented)).run_once()
        body = detail(client, session_id)
        assert body["turn"]["status"] == "failed" and body["turn"]["failureCode"] == "invalid-output"
        assert body["session"]["state"] == "discovering"  # the session does not fail
        assert body["questions"][0]["answer"]["value"] == ["Cards"]
        assert body["version"]["version"] == 1  # nothing was stored for the failed turn
        assert answer(client, session_id, [], advance=True).status_code == 409  # retry, not a new turn

        retried = client.post(f"{SESSIONS}/{session_id}/turns/retry")
        assert retried.json()["turn"] == {**retried.json()["turn"], "status": "queued", "tries": 2}
        assert client.post(f"{SESSIONS}/{session_id}/turns/retry").json()["turn"]["tries"] == 2  # idempotent
        assert make_worker(ScriptedProvider(READY_TURN)).run_once()
        assert detail(client, session_id)["session"]["state"] == "ready-for-review"

    def test_multi_tenant_isolation_is_enforced(self, signed_in, make_worker) -> None:
        multi = analyst_context(tenancy="multi")
        missing = analyst_json(context=multi)
        isolation = requirement_op(
            statement="Each workspace's data is visible only to its members.",
            kind="non-functional",
            source="inferred",
            confidence="medium",
            evidence=[],
            tags=["tenant-isolation"],
            acceptance_criteria=["A member of workspace A gets 404 for workspace B's records."],
        )
        present = analyst_json(context=multi, operations=[requirement_op(), isolation])
        client, _, session_id = discovered(signed_in, make_worker, missing, present)
        body = detail(client, session_id)
        assert [a["outcome"] for a in body["attempts"]] == ["invalid-output", "succeeded"]
        assert any("tenant-isolation" in p for p in body["attempts"][0]["validationErrors"])
        tags = {r["id"]: r["tags"] for r in body["version"]["content"]["requirements"]}
        assert tags["REQ-002"] == ["tenant-isolation"]

    def test_provider_failures(self, signed_in, make_worker) -> None:
        client, _, session_id = discovered(signed_in, make_worker, model_error("timeout"), analyst_json())
        assert [a["outcome"] for a in detail(client, session_id)["attempts"]] == ["provider-error", "succeeded"]

        other = signed_in("auth@example.com")
        project_id = create_project(other)
        sid = start_session(other, project_id).json()["id"]
        provider = ScriptedProvider(model_error("auth", "The model provider rejected the configured credentials."))
        assert make_worker(provider).run_once()
        body = detail(other, sid)
        assert body["turn"]["status"] == "failed" and body["turn"]["failureCode"] == "provider-auth"
        assert body["session"]["state"] == "discovering" and len(provider.requests) == 1  # not retried

    def test_oversized_context_fails_without_calling_the_provider(self, signed_in, make_worker) -> None:
        client = signed_in()
        session_id = start_session(client, create_project(client)).json()["id"]
        provider = ScriptedProvider()
        worker = make_worker(provider, analyst_request_token_budget=2048, analyst_max_output_tokens=1024)
        assert worker.run_once()
        body = detail(client, session_id)
        assert body["turn"]["failureCode"] == "context-too-large" and provider.requests == []


class TestWorkerRecovery:
    def test_duplicate_delivery_cannot_commit_a_turn_twice(self, signed_in, make_worker, clock, factory) -> None:
        client = signed_in()
        session_id = start_session(client, create_project(client)).json()["id"]
        late = make_worker(ScriptedProvider(), owner="worker-late")

        def slow_generation(_request) -> str:
            clock.advance(61)  # the lease expires and another worker re-delivers and finishes the turn
            assert make_worker(ScriptedProvider(analyst_json()), owner="worker-fast").run_once()
            return analyst_json()

        late._discovery._provider = ScriptedProvider(slow_generation)
        assert late.process(late.claim()) == "lost-lease"
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(DiscoveryQuestion)) == 1
            assert session.scalar(select(func.count()).select_from(RequirementsVersion)) == 1
        assert detail(client, session_id)["turn"]["status"] == "completed"

    def test_recovers_after_a_crash_and_exhaustion_fails_only_the_turn(
        self, signed_in, make_worker, clock, settings
    ) -> None:
        client = signed_in()
        session_id = start_session(client, create_project(client)).json()["id"]
        assert make_worker(ScriptedProvider(), owner="crashed").claim() is not None
        clock.advance(61)
        assert make_worker(ScriptedProvider(analyst_json()), owner="survivor").run_once()
        assert detail(client, session_id)["turn"]["status"] == "completed"

        answer(client, session_id, [{"questionKey": "DQ-001", "value": ["Cards"]}])
        for index in range(settings.job_max_deliveries):
            assert make_worker(ScriptedProvider(), owner=f"crash-{index}").claim() is not None
            clock.advance(61)
        assert make_worker(ScriptedProvider(), owner="final").claim() is None
        body = detail(client, session_id)
        assert body["turn"]["status"] == "failed" and body["turn"]["failureCode"] == "worker-exhausted"
        assert body["session"]["state"] == "discovering" and body["questions"][0]["answer"]["value"] == ["Cards"]

    def test_cancellation(self, signed_in, make_worker, factory) -> None:
        client = signed_in()
        session_id = start_session(client, create_project(client)).json()["id"]
        cancelled = client.post(f"{SESSIONS}/{session_id}/cancel")
        assert cancelled.json()["session"]["state"] == "cancelled" and cancelled.json()["turn"]["status"] == "cancelled"
        assert client.post(f"{SESSIONS}/{session_id}/cancel").status_code == 200  # idempotent
        assert not make_worker(ScriptedProvider()).run_once()  # the job was cancelled too
        with factory() as session:
            assert session.scalar(select(Job.status)) == "cancelled"


class TestApproval:
    def test_submit_requires_readiness_and_the_latest_version(self, signed_in, make_worker) -> None:
        client, _, session_id = discovered(signed_in, make_worker)
        assert submit(client, session_id, 1).status_code == 409  # not ready
        answer(client, session_id, [{"questionKey": "DQ-001", "value": ["Cards"]}])
        make_worker(ScriptedProvider(READY_TURN)).run_once()
        assert submit(client, session_id, 1).status_code == 409  # stale version
        assert submit(client, session_id, 0).status_code == 422

    def test_request_changes_needs_a_comment_and_starts_a_revision_turn(self, signed_in, make_worker) -> None:
        client, _, session_id = discovered(signed_in, make_worker)
        answer(client, session_id, [{"questionKey": "DQ-001", "value": ["Cards"]}])
        make_worker(ScriptedProvider(READY_TURN)).run_once()
        submit(client, session_id, 2)
        assert decide(client, session_id, "request-changes", 2).status_code == 422
        changed = decide(client, session_id, "request-changes", 2, comment="Add gift cards")
        assert changed.json()["session"]["state"] == "needs-changes"
        assert changed.json()["turn"] == {**changed.json()["turn"], "trigger": "revision", "status": "queued"}

        revision = analyst_json(
            operations=[
                requirement_op(
                    statement="Shoppers can pay with gift cards.", source="inferred", confidence="medium", evidence=[]
                )
            ],
            questions=[],
            readiness={"ready": True, "blockers": []},
        )
        provider = ScriptedProvider(revision)
        assert make_worker(provider).run_once()
        assert "<revision_request>\nAdd gift cards" in provider.requests[0].user_content
        body = detail(client, session_id)
        assert body["session"]["state"] == "ready-for-review" and body["version"]["version"] == 3
        statuses = [a["status"] for a in body["approvals"]]
        assert statuses == ["revision-requested"]
        stale = client.post(
            f"{SESSIONS}/{session_id}/approvals/{body['approvals'][0]['id']}",
            json={"decision": "approve", "version": 2},
        )
        assert stale.status_code == 409

    def test_versions_diffs_and_immutability(self, signed_in, make_worker, engine) -> None:
        client, _, session_id = approved_session(signed_in, make_worker)
        versions = client.get(f"{SESSIONS}/{session_id}/versions").json()
        assert [(v["version"], v["ready"]) for v in versions] == [(1, False), (2, True)]
        assert versions[1]["approvedAt"] and versions[1]["frozenAt"] and versions[0]["frozenAt"] is None
        diff = client.get(f"{SESSIONS}/{session_id}/versions/2", params={"diff": 1}).json()["diff"]
        assert diff == {"fromVersion": 1, "added": ["REQ-002"], "deprecated": [], "changed": [], "contextFields": []}
        assert client.get(f"{SESSIONS}/{session_id}/versions/9").status_code == 404
        assert client.get(f"{SESSIONS}/{session_id}/versions/0").status_code == 422
        assert client.get(f"{SESSIONS}/{session_id}/versions/2", params={"diff": 9}).status_code == 404

        with pytest.raises(DBAPIError, match="immutable"), engine.begin() as connection:
            connection.execute(text("UPDATE requirements_versions SET content = '{}' WHERE version = 2"))
        with pytest.raises(DBAPIError, match="immutable"), engine.begin() as connection:
            connection.execute(text("UPDATE requirements_versions SET approved_at = now() WHERE version = 2"))

    def test_a_new_session_continues_from_the_approved_version_with_stable_ids(self, signed_in, make_worker) -> None:
        client, project_id, _ = approved_session(signed_in, make_worker)
        second = start_session(client, project_id, key="session-key-0003").json()["id"]
        update = analyst_json(
            operations=[
                requirement_op(op="update", id="REQ-001", statement="Shoppers can browse and search products."),
                requirement_op(
                    statement="Shoppers can track orders.", source="inferred", confidence="low", evidence=[]
                ),
            ],
            questions=[],
        )
        provider = ScriptedProvider(update)
        assert make_worker(provider).run_once()
        assert '"id":"REQ-002"' in provider.requests[0].user_content
        version = detail(client, second)["version"]
        assert [r["id"] for r in version["content"]["requirements"]] == ["REQ-001", "REQ-002", "REQ-003"]
        approved_id = client.get(f"{PROJECTS}/{project_id}/requirements/approved").json()["version"]["id"]
        assert version["parentVersionId"] == approved_id


class TestAuthorization:
    def test_owner_only_csrf_and_samples(self, signed_in, make_worker, make_client) -> None:
        client, project_id, session_id = discovered(signed_in, make_worker)
        intruder = signed_in("intruder@example.com")
        assert intruder.get(f"{SESSIONS}/{session_id}").status_code == 404
        assert answer(intruder, session_id, [{"questionKey": "DQ-001", "value": ["Cards"]}]).status_code == 404
        assert intruder.post(f"{SESSIONS}/{session_id}/cancel").status_code == 404
        assert intruder.get(f"{SESSIONS}/{session_id}/versions").status_code == 404
        assert intruder.get(f"{PROJECTS}/{project_id}/requirements/approved").status_code == 404
        assert intruder.get(f"/api/v1/runs/{session_id}/events/history").status_code == 404
        assert start_session(intruder, project_id, key="session-key-0009").status_code == 404

        anonymous = make_client()
        assert anonymous.get(f"{SESSIONS}/{session_id}").status_code == 401
        no_csrf = client.__class__(client.app, cookies=client.cookies)
        assert no_csrf.post(f"{SESSIONS}/{session_id}/cancel").status_code == 403

        assert start_session(client, "sample_fashion-store").json()["error"]["code"] == "read-only"
        assert client.get(f"{PROJECTS}/{project_id}/requirements/approved").status_code == 404  # none approved yet
        assert client.get(f"{SESSIONS}/{uuid.uuid4()}").status_code == 404
        assert client.get(f"{SESSIONS}/not-a-uuid").status_code == 422

    def test_start_requires_a_configured_provider(self, settings, factory, clock) -> None:
        from fastapi.testclient import TestClient

        from omniora_api.app import create_app

        app = create_app(settings, factory=factory, provider_configured=False, clock=clock)
        client = TestClient(app, headers={"X-Omniora-Client": "web"})
        client.post(
            "/api/v1/auth/register", json={"name": "Ada", "email": "ada@example.com", "password": "correct horse"}
        )
        response = start_session(client, create_project(client))
        assert response.status_code == 503 and "GROQ_API_KEY" in response.json()["error"]["message"]
