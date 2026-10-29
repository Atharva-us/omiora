"""Durable runs: start/idempotency, worker recovery and duplicate delivery, approvals, cancellation, SSE."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import func, select

from omniora_api.audit import verify_audit_chain
from omniora_api.db.models import AgentAttempt, Job, PlanVersion, RunEvent
from omniora_api.worker.planning import LeaseState
from omniora_api.worker.runner import LeaseKeeper

from .support import ScriptedProvider, configuration, model_error, plan, plan_json

PROJECTS = "/api/v1/projects"


def create_project(client, **overrides) -> str:
    return client.post(PROJECTS, json=configuration(**overrides)).json()["id"]


def start(client, project_id: str, key: str = "key-00000001"):
    # These tests cover the planning engine itself, so they use the explicit plan-without-requirements
    # path; planning from approved requirements is covered in test_requirements_api.py.
    return client.post(
        f"{PROJECTS}/{project_id}/runs", headers={"Idempotency-Key": key}, json={"withoutRequirements": True}
    )


def detail(client, run_id: str) -> dict:
    return client.get(f"/api/v1/runs/{run_id}").json()


def events(client, run_id: str, after: int = 0) -> list[dict]:
    return client.get(f"/api/v1/runs/{run_id}/events/history", params={"after": after}).json()


def planned_run(signed_in, make_worker, *outputs: str):
    client = signed_in()
    project_id = create_project(client)
    run_id = start(client, project_id).json()["id"]
    assert make_worker(ScriptedProvider(*(outputs or (plan_json(),)))).run_once()
    return client, project_id, run_id


class TestStartingRuns:
    def test_start_is_idempotent_and_single_active(self, signed_in, factory) -> None:
        client = signed_in()
        project_id = create_project(client)
        first = start(client, project_id)
        assert first.status_code == 202 and first.json()["state"] == "queued"
        repeat = start(client, project_id)
        assert repeat.status_code == 200 and repeat.json()["id"] == first.json()["id"]
        conflict = start(client, project_id, key="key-00000002")
        assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "conflict"
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(Job)) == 1  # one job, despite the retry

    def test_requires_a_well_formed_idempotency_key(self, signed_in) -> None:
        client = signed_in()
        project_id = create_project(client)
        assert client.post(f"{PROJECTS}/{project_id}/runs").status_code == 422
        assert start(client, project_id, key="short").status_code == 422

    def test_provider_must_be_configured(self, settings, factory, clock, signed_in) -> None:
        from fastapi.testclient import TestClient

        from omniora_api.app import create_app

        app = create_app(settings, factory=factory, provider_configured=False, clock=clock)
        client = TestClient(app, headers={"X-Omniora-Client": "web"})
        client.post(
            "/api/v1/auth/register", json={"name": "Ada", "email": "ada@example.com", "password": "correct horse"}
        )
        project_id = create_project(client)
        response = start(client, project_id)
        assert response.status_code == 503
        assert "ANTHROPIC_API_KEY" in response.json()["error"]["message"]

    def test_hourly_limit(self, signed_in, settings, factory, clock) -> None:
        client = signed_in()
        for index in range(settings.runs_per_user_per_hour):
            project_id = create_project(client, name=f"P{index}")
            assert start(client, project_id, key=f"key-{index:08d}").status_code == 202
        limited = start(client, create_project(client, name="One more"), key="key-99999999")
        assert limited.status_code == 429 and limited.headers["Retry-After"] == "3600"
        clock.advance(3601)
        assert start(client, create_project(client, name="Later"), key="key-88888888").status_code == 202

    def test_samples_and_foreign_projects_cannot_be_planned(self, signed_in) -> None:
        owner, intruder = signed_in("o@example.com"), signed_in("i@example.com")
        project_id = create_project(owner)
        assert start(intruder, project_id).status_code == 404
        assert start(owner, "sample_fashion-store").json()["error"]["code"] == "read-only"


class TestWorker:
    def test_happy_path_persists_plan_tasks_approval_and_events(self, signed_in, make_worker, factory) -> None:
        client, _, run_id = planned_run(signed_in, make_worker)
        body = detail(client, run_id)
        assert body["run"]["state"] == "awaiting-approval" and body["run"]["currentPlanVersion"] == 1
        assert body["plan"]["content"]["openQuestions"][0]["whyItMatters"]
        assert body["plan"]["content"]["recommendedStack"]["technologies"] == ["nextjs", "postgresql"]
        assert [t["key"] for t in body["tasks"]] == ["T1", "T2", "T3"]
        assert body["tasks"][2]["dependsOn"] == ["T1", "T2"] and body["tasks"][0]["status"] == "proposed"
        assert [a["status"] for a in body["approvals"]] == ["pending"]
        assert [a["outcome"] for a in body["attempts"]] == ["succeeded"]
        types = [e["type"] for e in events(client, run_id)]
        assert types == [
            "run.created",
            "run.state-changed",
            "attempt.started",
            "attempt.finished",
            "plan.created",
            "approval.requested",
            "run.state-changed",
        ]
        assert [e["seq"] for e in events(client, run_id)] == list(range(1, 8))
        with factory() as session:
            assert verify_audit_chain(session) is None

    def test_invalid_output_is_retried_then_persisted(self, signed_in, make_worker) -> None:
        cyclic = plan()
        cyclic["tasks"][0]["depends_on"] = ["T3"]
        client, _, run_id = planned_run(signed_in, make_worker, "not json", json.dumps(cyclic), plan_json())
        attempts = detail(client, run_id)["attempts"]
        assert [a["outcome"] for a in attempts] == ["invalid-output", "invalid-output", "succeeded"]
        assert any("cycle" in problem for problem in attempts[1]["validationErrors"])

    def test_exhausted_attempts_fail_the_run(self, signed_in, make_worker) -> None:
        client, _, run_id = planned_run(signed_in, make_worker, "{}", "{}", "{}")
        run = detail(client, run_id)["run"]
        assert run["state"] == "failed" and run["failureCode"] == "invalid-plan"
        assert detail(client, run_id)["plan"] is None

    def test_provider_misconfiguration_fails_fast_with_a_safe_message(self, signed_in, make_worker) -> None:
        provider = ScriptedProvider(model_error("auth", "The model provider rejected the configured credentials."))
        client = signed_in()
        run_id = start(client, create_project(client)).json()["id"]
        make_worker(provider).run_once()
        run = detail(client, run_id)["run"]
        assert run["failureCode"] == "provider-auth" and len(provider.requests) == 1

    def test_recovers_after_worker_interruption(self, signed_in, make_worker, clock, factory) -> None:
        client = signed_in()
        run_id = start(client, create_project(client)).json()["id"]
        crashed = make_worker(ScriptedProvider(), owner="worker-crashed")
        assert crashed.claim() is not None  # claimed, then the process "dies" without finishing
        survivor = make_worker(ScriptedProvider(plan_json()), owner="worker-survivor")
        assert survivor.claim() is None  # lease still valid: no double processing
        clock.advance(61)
        assert survivor.run_once()
        assert detail(client, run_id)["run"]["state"] == "awaiting-approval"
        with factory() as session:
            job = session.scalar(select(Job))
            assert job.deliveries == 2 and job.status == "done"

    def test_duplicate_delivery_cannot_commit_twice(self, signed_in, make_worker, clock, factory) -> None:
        client = signed_in()
        run_id = start(client, create_project(client)).json()["id"]
        late = make_worker(ScriptedProvider(), owner="worker-late")

        def slow_generation(_request) -> str:
            # While the first worker is "stuck" in the model call, its lease expires and the job is re-delivered.
            clock.advance(61)
            assert make_worker(ScriptedProvider(plan_json()), owner="worker-fast").run_once()
            return plan_json()

        late._planning._provider = ScriptedProvider(slow_generation)
        job = late.claim()
        assert late.process(job) == "lost-lease"
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(PlanVersion)) == 1
            assert session.scalar(select(func.count()).select_from(AgentAttempt)) == 2  # both attempts are on record
        assert detail(client, run_id)["run"]["state"] == "awaiting-approval"

    def test_delivery_limit_fails_the_run(self, signed_in, make_worker, clock, settings) -> None:
        client = signed_in()
        run_id = start(client, create_project(client)).json()["id"]
        for index in range(settings.job_max_deliveries):
            assert make_worker(ScriptedProvider(), owner=f"crash-{index}").claim() is not None
            clock.advance(61)
        assert make_worker(ScriptedProvider(), owner="final").claim() is None
        run = detail(client, run_id)["run"]
        assert run["state"] == "failed" and run["failureCode"] == "worker-exhausted"

    def test_unexpected_errors_are_retried_with_backoff(self, signed_in, make_worker, clock, factory) -> None:
        client = signed_in()
        start(client, create_project(client))

        def explode(_request) -> str:
            raise RuntimeError("bug")

        worker = make_worker(ScriptedProvider(explode))
        assert worker.run_once()
        with factory() as session:
            job = session.scalar(select(Job))
            assert job.status == "queued" and job.available_at > clock() and job.last_error == "RuntimeError"

    def test_cancellation_discards_in_flight_results(self, signed_in, make_worker) -> None:
        client = signed_in()
        run_id = start(client, create_project(client)).json()["id"]

        def cancel_meanwhile(_request) -> str:
            assert client.post(f"/api/v1/runs/{run_id}/cancel").json()["state"] == "cancelled"
            return plan_json()

        make_worker(ScriptedProvider(cancel_meanwhile)).run_once()
        body = detail(client, run_id)
        assert body["run"]["state"] == "cancelled" and body["plan"] is None

    def test_lease_keeper_detects_a_lost_lease(self, signed_in, make_worker, clock, factory) -> None:
        client = signed_in()
        start(client, create_project(client))
        job = make_worker(ScriptedProvider(), owner="holder").claim()
        clock.advance(61)
        make_worker(ScriptedProvider(), owner="thief").claim()  # re-delivered elsewhere
        lease = LeaseState()
        keeper = LeaseKeeper(factory, job.id, "holder", 0.03, lease, clock)  # renews every 10 ms
        keeper.start()
        keeper.join(timeout=2)
        assert lease.lost


class TestApprovals:
    def decide(self, client, run_id: str, decision: str, version: int = 1, comment: str | None = None):
        approval_id = detail(client, run_id)["approvals"][-1]["id"]
        return client.post(
            f"/api/v1/runs/{run_id}/approvals/{approval_id}",
            json={"decision": decision, "planVersion": version, "comment": comment},
        ), approval_id

    def test_approve_is_idempotent_and_starts_nothing(self, signed_in, make_worker, factory) -> None:
        client, _, run_id = planned_run(signed_in, make_worker)
        response, approval_id = self.decide(client, run_id, "approve")
        assert response.status_code == 200 and response.json()["status"] == "approved"
        again = client.post(
            f"/api/v1/runs/{run_id}/approvals/{approval_id}", json={"decision": "approve", "planVersion": 1}
        )
        assert again.status_code == 200 and again.json() == response.json()
        conflicting = client.post(
            f"/api/v1/runs/{run_id}/approvals/{approval_id}", json={"decision": "reject", "planVersion": 1}
        )
        assert conflicting.status_code == 409
        assert detail(client, run_id)["run"]["state"] == "approved"
        with factory() as session:  # approval queued no further work
            assert session.scalar(select(func.count()).select_from(Job).where(Job.status == "queued")) == 0

    def test_reject_is_terminal(self, signed_in, make_worker) -> None:
        client, _, run_id = planned_run(signed_in, make_worker)
        assert self.decide(client, run_id, "reject", comment="Not now")[0].json()["status"] == "rejected"
        assert detail(client, run_id)["run"]["state"] == "rejected"
        assert client.post(f"/api/v1/runs/{run_id}/cancel").status_code == 409

    def test_revision_creates_a_new_version_and_stale_approvals_fail(self, signed_in, make_worker) -> None:
        client, _, run_id = planned_run(signed_in, make_worker)
        assert self.decide(client, run_id, "revise")[0].status_code == 422  # a revision needs a comment
        response, old_approval = self.decide(client, run_id, "revise", comment="Add an admin dashboard")
        assert response.json()["status"] == "revision-requested"
        assert detail(client, run_id)["run"]["state"] == "queued"

        provider = ScriptedProvider(plan_json(summary="Revised plan with an admin dashboard."))
        make_worker(provider).run_once()
        assert "<revision_request>" in provider.requests[0].user_content
        assert "Add an admin dashboard" in provider.requests[0].user_content
        body = detail(client, run_id)
        assert body["run"]["currentPlanVersion"] == 2 and body["plan"]["version"] == 2
        assert [a["status"] for a in body["approvals"]] == ["revision-requested", "pending"]

        # An approval for version 1 (or a v1 approval id) must not approve version 2.
        stale = client.post(
            f"/api/v1/runs/{run_id}/approvals/{old_approval}", json={"decision": "approve", "planVersion": 1}
        )
        assert stale.status_code == 409
        new_approval = body["approvals"][-1]["id"]
        wrong_version = client.post(
            f"/api/v1/runs/{run_id}/approvals/{new_approval}", json={"decision": "approve", "planVersion": 1}
        )
        assert wrong_version.status_code == 409
        assert self.decide(client, run_id, "approve", version=2)[0].json()["status"] == "approved"

    def test_only_the_owner_can_decide(self, signed_in, make_worker) -> None:
        client, _, run_id = planned_run(signed_in, make_worker)
        approval_id = detail(client, run_id)["approvals"][0]["id"]
        intruder = signed_in("intruder@example.com")
        response = intruder.post(
            f"/api/v1/runs/{run_id}/approvals/{approval_id}", json={"decision": "approve", "planVersion": 1}
        )
        assert response.status_code == 404
        assert intruder.get(f"/api/v1/runs/{run_id}").status_code == 404
        anonymous = client.__class__(client.app, headers={"X-Omniora-Client": "web"})
        assert anonymous.get(f"/api/v1/runs/{run_id}").status_code == 401

    def test_decisions_on_cancelled_runs_conflict(self, signed_in, make_worker) -> None:
        client, _, run_id = planned_run(signed_in, make_worker)
        client.post(f"/api/v1/runs/{run_id}/cancel")
        assert client.post(f"/api/v1/runs/{run_id}/cancel").status_code == 200  # idempotent
        response, _ = self.decide(client, run_id, "approve")
        assert response.status_code == 409


class TestServerSentEvents:
    def read_stream(self, client, run_id: str, last_event_id: str | None = None) -> list[dict]:
        headers = {"Last-Event-ID": last_event_id} if last_event_id else {}
        parsed, current = [], {}
        with client.stream("GET", f"/api/v1/runs/{run_id}/events", headers=headers) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            for line in response.iter_lines():
                if not line:
                    if current:
                        parsed.append(current)
                    current = {}
                elif not line.startswith(":"):
                    field, _, value = line.partition(": ")
                    current[field] = value
        return parsed

    def test_replays_and_resumes_after_last_event_id(self, signed_in, make_worker) -> None:
        client, _, run_id = planned_run(signed_in, make_worker)
        TestApprovals().decide(client, run_id, "approve")  # terminal, so the stream ends
        full = [e for e in self.read_stream(client, run_id) if "id" in e]
        assert [int(e["id"]) for e in full] == list(range(1, len(full) + 1))
        assert full[-1]["event"] == "run.state-changed"
        resumed = self.read_stream(client, run_id, last_event_id="4")
        ids = [int(e["id"]) for e in resumed if "id" in e]
        assert ids == list(range(5, len(full) + 1))  # nothing missed, nothing repeated
        assert resumed[-1]["event"] == "end" and json.loads(resumed[-1]["data"]) == {"state": "approved"}
        assert json.loads(full[0]["data"])["type"] == "run.created"

    def test_stream_is_authorised_and_validates_the_cursor(self, signed_in, make_worker) -> None:
        client, _, run_id = planned_run(signed_in, make_worker)
        assert signed_in("other@example.com").get(f"/api/v1/runs/{run_id}/events").status_code == 404
        assert client.get(f"/api/v1/runs/{run_id}/events", headers={"Last-Event-ID": "abc"}).status_code == 422
        assert client.get(f"/api/v1/runs/{uuid.uuid4()}/events").status_code == 404

    def test_event_sequence_is_gap_free_in_the_database(self, signed_in, make_worker, factory) -> None:
        client, _, run_id = planned_run(signed_in, make_worker)
        TestApprovals().decide(client, run_id, "revise", comment="More detail")
        make_worker(ScriptedProvider(plan_json())).run_once()
        with factory() as session:
            seqs = list(
                session.scalars(select(RunEvent.seq).where(RunEvent.run_id == uuid.UUID(run_id)).order_by(RunEvent.id))
            )
        assert seqs == list(range(1, len(seqs) + 1))


@pytest.mark.parametrize(
    "bad_decision", [{"decision": "maybe", "planVersion": 1}, {"decision": "approve", "planVersion": 0}]
)
def test_decision_body_validation(signed_in, make_worker, bad_decision) -> None:
    client, _, run_id = planned_run(signed_in, make_worker)
    approval_id = detail(client, run_id)["approvals"][0]["id"]
    assert client.post(f"/api/v1/runs/{run_id}/approvals/{approval_id}", json=bad_decision).status_code == 422
