"""Live production-path check for Agent 2 -> Agent 1 (makes real, billed model calls).

    cd backend
    export OMNIORA_MODEL_PROVIDER=groq OMNIORA_DATABASE_URL=postgresql://.../omniora_live_check
    python scripts/live_requirements_check.py [--cleanup]

Uses only production code: the FastAPI app (authenticated, CSRF-checked requests), the Worker with
both job handlers, the provider chosen by `build_planning_provider` (never the scripted test provider),
and PostgreSQL. It is not part of the test suite. It prints no credentials and no raw model output;
the full attempts (including rejected outputs) stay in `agent_attempts`.

Safety:
- It refuses to run unless the database name contains "live", "test", "e2e", or "scratch".
- Each run registers a fresh user, so a re-run never collides with earlier data. Failed runs leave their
  data in place for inspection; `--cleanup` deletes this run's user (and, by cascade, its projects, runs,
  attempts, and requirements). Audit rows are append-only and stay.
- Model use is bounded: the settings' per-turn attempt limit, one retry of a failed turn, at most
  MAX_TURNS discovery turns, and a cap on reported tokens (MAX_REPORTED_TOKENS) checked between steps.

Scenarios, reported separately:
  A  multi-tenant discovery: tenancy `multi`, a mandatory `tenant-isolation` requirement whose criteria
     express denial, and an accepted, ready version
  B  planning from that exact approved version: the run pins its id, version and hash; every approved
     must-have is covered or flagged; the plan is accepted by the production validator and awaits approval
  C  the whole path (authenticated API, events, persistence, approval gates, integrity checks)

Answers to the analyst's real questions are chosen by question kind and topic (see `answer`) and printed,
so a run is reproducible and nothing is presented as a real user's input.
"""

from __future__ import annotations

import json
import secrets
import sys
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from omniora_api.app import create_app
from omniora_api.audit import verify_audit_chain
from omniora_api.config import get_settings
from omniora_api.db.models import RequirementsVersion
from omniora_api.db.session import make_engine, make_session_factory, transaction
from omniora_api.domain.plans import find_cycle
from omniora_api.domain.requirements import RequirementsDocument, content_sha256
from omniora_api.llm.factory import build_planning_provider
from omniora_api.worker.discovery import DiscoveryJobHandler
from omniora_api.worker.planning import PlanningJobHandler
from omniora_api.worker.runner import Worker

MAX_TURNS = 3
MAX_REPORTED_TOKENS = 70_000
SAFE_DATABASE_MARKERS = ("live", "test", "e2e", "scratch")
DENIAL_WORDS = ("denied", "deny", "denies", "404", "403", "forbidden", "cannot", "rejected", "refused", "no access")
BRIEF = {
    "name": "Studio Booking Cloud",
    "description": "A booking platform where independent yoga studios each manage their own classes, instructors, "
    "and members. Members book and cancel classes at their studio.",
    "platform": "website",
    "referenceUrl": "",
    "stack": {"mode": "recommend"},
    "requirements": {"features": ["authentication", "database"], "custom": "Each studio's data is private to it."},
}
FREE_TEXT = {
    "users": "Studio owners, instructors, and members. Members only see their own studio.",
    "scope": "Studios publish a class timetable; members book and cancel; owners manage instructors and members.",
}


def answer(question: dict) -> object:
    """Deterministic stand-in answers by kind and topic. A tenancy yes/no is answered yes only when it asks
    whether separate organisations share the deployment, which the brief already says."""
    kind, options, topic = question["kind"], question["options"], question["topic"]
    if kind == "free-text":
        return FREE_TEXT.get(topic, "Keep it simple for the first version; nothing beyond the brief.")
    if kind == "yes-no":
        return topic != "tenancy" or "share" in question["prompt"].lower()
    if kind == "multiple-choice":
        return options[:1]
    return options[0]


class Report:
    """Collects pass/fail per scenario so a failure in one is not hidden by the others."""

    def __init__(self) -> None:
        self.results: dict[str, list[tuple[str, bool]]] = {"A": [], "B": [], "C": []}

    def check(self, scenario: str, label: str, ok: bool) -> bool:
        self.results[scenario].append((label, bool(ok)))
        print(f"   [{scenario}] {'PASS' if ok else 'FAIL'}: {label}")
        return bool(ok)

    def summary(self) -> int:
        print("\nSummary (live results; scripted tests are reported separately):")
        failed = 0
        for scenario, rows in self.results.items():
            bad = [label for label, ok in rows if not ok]
            status = "not reached" if not rows else ("PASSED" if not bad else "FAILED")
            failed += bool(bad) or not rows
            print(
                f"  Scenario {scenario}: {status} ({len(rows) - len(bad)}/{len(rows)} checks)"
                + "".join(f"\n    - {b}" for b in bad)
            )
        return 1 if failed else 0


def stream_summary(client: TestClient, run_id: str) -> tuple[list[int], bool]:
    """Reads the SSE stream of a finished session: event ids replayed and whether `end` was sent."""
    ids: list[int] = []
    ended = False
    with client.stream("GET", f"/api/v1/runs/{run_id}/events") as response:
        for line in response.iter_lines():
            if line.startswith("id: "):
                ids.append(int(line[4:]))
            elif line.startswith("event: end"):
                ended = True
    return ids, ended


def main() -> int:
    settings = get_settings()
    database = make_url(settings.database_url).database or ""
    if not any(marker in database for marker in SAFE_DATABASE_MARKERS):
        print(
            f"Refusing to run against database {database!r}: use a disposable one (name containing "
            f"{', '.join(SAFE_DATABASE_MARKERS)})."
        )
        return 2
    factory = make_session_factory(make_engine(settings.database_url))
    provider = build_planning_provider(settings)
    print(f"provider={provider.name} model={provider.model} configured={provider.configured} database={database}")
    if not provider.configured:
        return 2
    cleanup = "--cleanup" in sys.argv
    worker = Worker(
        factory,
        PlanningJobHandler(factory, provider, settings),
        discovery=DiscoveryJobHandler(factory, provider, settings),
        owner="live-requirements-check",
    )
    client = TestClient(
        create_app(settings, factory=factory), headers={"X-Omniora-Client": "web", "Origin": settings.cors_origins[0]}
    )
    report = Report()
    usage = {"input": 0, "output": 0, "calls": 0}
    seen: set[tuple[int, int, str]] = set()

    def key() -> str:
        return f"live-{uuid.uuid4().hex}"

    def record(attempts: list[dict], label: str) -> None:
        for a in attempts:
            ident = (a.get("turn", a.get("planVersion", 0)), a["attempt"], a["createdAt"])
            if ident in seen:
                continue
            seen.add(ident)
            usage["calls"] += 1
            usage["input"] += a["inputTokens"] or 0
            usage["output"] += a["outputTokens"] or 0
            print(
                f"   {label} attempt {a['attempt']}: {a['outcome']} {a['errorCode'] or ''} in={a['inputTokens']} "
                f"out={a['outputTokens']} {a['latencyMs']}ms problems={a['validationErrors'][:2]}"
            )

    def over_budget() -> bool:
        total = usage["input"] + usage["output"]
        if total > MAX_REPORTED_TOKENS:
            print(f"STOPPED: reported tokens {total} exceed the cap of {MAX_REPORTED_TOKENS}.")
        return total > MAX_REPORTED_TOKENS

    email = f"live-{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/api/v1/auth/register", json={"name": "Live", "email": email, "password": secrets.token_urlsafe(18)}
    ).raise_for_status()
    user_id = client.get("/api/v1/auth/me").json()["id"]
    try:
        return run(client, factory, worker, report, record, over_budget, usage, key)
    finally:
        if cleanup:
            try:
                with transaction(factory) as session:
                    session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
                print("cleanup: this run's user and its cascaded data were deleted")
            except Exception as error:
                print("cleanup failed:", type(error).__name__)
        else:
            print(f"data kept for inspection (user {email}); re-run with --cleanup to delete it")


def run(client, factory, worker, report, record, over_budget, usage, key) -> int:
    check = report.check
    pid = client.post("/api/v1/projects", json=BRIEF).json()["id"]
    refused = client.post(f"/api/v1/projects/{pid}/runs", headers={"Idempotency-Key": key()})
    print("1. planning before approval:", refused.status_code, refused.json()["error"]["code"])
    check("C", "planning is refused without approved requirements (409)", refused.status_code == 409)

    session = client.post(f"/api/v1/projects/{pid}/requirements-sessions", headers={"Idempotency-Key": key()})
    sid = session.json()["id"]
    print("2. discovery session started:", sid)
    detail: dict = {}
    retried = False
    for _ in range(MAX_TURNS):
        print("3. worker processed a job:", worker.run_once())
        detail = client.get(f"/api/v1/requirements-sessions/{sid}").json()
        turn = detail["turn"]
        record(detail["attempts"], f"turn {turn['number']}")
        if turn["status"] == "failed":
            print(f"   turn failed: {turn['failureCode']} {turn['failureMessage']}")
            if retried:
                print("STOPPED: the turn failed twice.")
                check("A", "a requirements version was accepted (turn failed twice)", False)
                return report.summary()
            retried = True
            client.post(f"/api/v1/requirements-sessions/{sid}/turns/retry")
            continue
        content = detail["version"]["content"]
        print(
            f"4-6. persisted v{detail['version']['version']} state={detail['session']['state']} "
            f"tenancy={content['context']['tenancy']} ready={content['readiness']['ready']} "
            f"requirements={[(r['id'], r['priority'], r['tags']) for r in content['requirements']]}"
        )
        if detail["session"]["state"] == "ready-for-review" or over_budget():
            break
        answers = []
        for q in [q for q in detail["questions"] if q["status"] == "open"]:
            value = answer(q)
            print(
                f"   {q['key']} [{q['kind']}, blocking={q['blocking']}, {q['topic']}] {q['prompt']}"
                f" -> {json.dumps(value)}"
            )
            answers.append({"questionKey": q["key"], "value": value})
        saved = client.post(
            f"/api/v1/requirements-sessions/{sid}/answers",
            headers={"Idempotency-Key": key()},
            json={"answers": answers, "advance": True},
        )
        print("8. answers submitted:", saved.status_code)
        check("C", "answers were accepted and the analyst resumed", saved.status_code == 200)
    else:
        print(f"STOPPED: not ready after {MAX_TURNS} turns; nothing was approved.")

    version = detail["version"]
    document = version["content"] if version else None
    ready = detail["session"]["state"] == "ready-for-review"
    check("A", "an accepted, ready requirements version exists", ready)
    if document:
        isolation = [r for r in document["requirements"] if "tenant-isolation" in r["tags"] and r["status"] == "active"]
        check("A", "tenancy identified as multi", document["context"]["tenancy"] == "multi")
        check("A", "a mandatory tenant-isolation requirement exists", any(r["priority"] == "must" for r in isolation))
        criteria = " ".join(c.lower() for r in isolation for c in r["acceptanceCriteria"])
        check("A", "its criteria express cross-tenant access denial", any(w in criteria for w in DENIAL_WORDS))
    check("C", "events were persisted for the session", bool(client.get(f"/api/v1/runs/{sid}/events/history").json()))
    if not ready or over_budget():
        return report.summary()

    number = version["version"]
    submitted = client.post(f"/api/v1/requirements-sessions/{sid}/submit", json={"version": number})
    check("C", "the ready version was submitted for approval", submitted.status_code == 200)
    approval = client.get(f"/api/v1/requirements-sessions/{sid}").json()["approvals"][-1]
    decided = client.post(
        f"/api/v1/requirements-sessions/{sid}/approvals/{approval['id']}",
        json={"decision": "approve", "version": number},
    )
    approved_response = client.get(f"/api/v1/projects/{pid}/requirements/approved")
    if not (
        check("C", "the version was approved", decided.status_code == 200) and approved_response.status_code == 200
    ):
        return report.summary()
    approved = approved_response.json()["version"]
    print(
        f"9. approved v{approved['version']} state={decided.json()['session']['state']}"
        f" sha256={approved['contentSha256'][:16]}"
    )
    ids, ended = stream_summary(client, sid)
    check("C", "the event stream replays all events and ends", ids == sorted(ids) and len(ids) > 3 and ended)

    with factory() as db:
        row = db.get(RequirementsVersion, uuid.UUID(approved["id"]))
        recomputed = content_sha256(RequirementsDocument.model_validate(row.content))
        check(
            "C",
            "stored content hashes to the recorded and approved hash",
            recomputed == row.content_sha256 == approved["contentSha256"],
        )
        check(
            "C", "the stored version is frozen and approved", row.frozen_at is not None and row.approved_at is not None
        )
    if over_budget():
        return report.summary()

    run = client.post(f"/api/v1/projects/{pid}/runs", headers={"Idempotency-Key": key()}).json()
    check("B", "the planning run pins the approved version id", run["pinnedRequirementsVersionId"] == approved["id"])
    print("10. worker processed a job:", worker.run_once())
    plan = client.get(f"/api/v1/runs/{run['id']}").json()
    record(plan["attempts"], "plan")
    pinned = plan["requirements"] or {}
    check(
        "B",
        "the run detail reports the pinned version number and hash",
        pinned.get("version") == approved["version"] and pinned.get("contentSha256") == approved["contentSha256"],
    )
    print(f"    run state={plan['run']['state']} failure={plan['run']['failureCode']} usage reported={usage}")
    check("B", "a plan was accepted by the production validator", plan["plan"] is not None)
    check("C", "the planning run awaits plan approval", plan["run"]["state"] == "awaiting-approval")
    if plan["plan"]:
        active = [r for r in approved["content"]["requirements"] if r["status"] == "active"]
        must = {r["id"] for r in active if r["priority"] == "must"}
        isolation_ids = {r["id"] for r in active if "tenant-isolation" in r["tags"]}
        covered = {rid for t in plan["tasks"] for rid in t["requirementIds"]}
        flagged = {f["id"] for f in plan["plan"]["content"]["flaggedRequirements"]}
        print("11. tasks:", [(t["key"], t["requirementIds"]) for t in plan["tasks"]])
        print(
            f"    must-haves covered {sorted(must & covered)} flagged {sorted(flagged)} "
            f"missing {sorted(must - covered - flagged)}"
        )
        check("B", "every approved must-have is covered or flagged with a reason", not (must - covered - flagged))
        check("B", "the tenant-isolation requirement is covered by a task", bool(isolation_ids & covered))
        known = {r["id"] for r in approved["content"]["requirements"]}
        derived = {r["id"] for r in plan["plan"]["content"]["requirements"]}
        check("B", "tasks reference only approved or derived (D-) ids", covered <= known | derived)
        check("B", "the plan does not restate approved requirements", not (derived & known))
        deps = {t["key"]: t["dependsOn"] for t in plan["tasks"]}
        check(
            "B",
            "the task graph is acyclic with resolvable dependencies",
            find_cycle(deps) is None and all(d in deps for ds in deps.values() for d in ds),
        )
        check("B", "every task is only proposed", {t["status"] for t in plan["tasks"]} == {"proposed"})
        check(
            "C",
            "a plan approval is pending for plan v1",
            [a["status"] for a in plan["approvals"]] == ["pending"] and plan["approvals"][0]["planVersion"] == 1,
        )
    with factory() as db:
        check("C", "the audit chain is intact", verify_audit_chain(db) is None)
    print("usage reported:", usage, "(rejected and rate-limited calls report no usage)")
    return report.summary()


if __name__ == "__main__":
    raise SystemExit(main())
