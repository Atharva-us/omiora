# Phase 2 implementation plan: backend foundation + Project Manager agent

Date: 2026-10-29. Scope: a separately runnable FastAPI backend, durable run infrastructure, a
provider-independent model interface, **Agent 1 (Project Manager) only**, the plan-approval lifecycle, and
frontend integration. Out of scope: Agents 2–10, code execution, sandboxes, and deployment.

## 0. Inputs and conflicts resolved

Read before planning: `docs/ARCHITECTURE.md`, `ENGINEERING_STANDARDS.md`, `BACKEND_CONTRACTS.md`,
`ARCHITECTURE_AUDIT.md`, `src/domain/**`, `src/services/**`, and the existing tests and scripts.

| Conflict found in the repository | Resolution |
| --- | --- |
| `services/contracts/engine.ts` `AgentRun.state` (`running`, `completed`) does not match an approval lifecycle | Replaced by the explicit run state machine in §3, defined once as a backend enum and mirrored as a Zod schema in `src/domain/runs/run.ts`. |
| `BACKEND_CONTRACTS.md` approvals carry no plan version, so a stale approval could approve a newer plan | Approvals reference an exact `plan_version`; the decision body must repeat it (§2.3). |
| Frontend `APP_ERROR_CODES` lacks codes the API needs | Add `unauthenticated` (401), `conflict` (409), and `rate-limited` (429). Existing codes keep their meaning. |
| `ProjectService.listProjects()` returns an array; the API paginates | The HTTP adapter follows `nextCursor` until exhausted (page size 100). This is documented as a limit for very large accounts. |
| The demo adapter's `prj_…` ids | Remain local-only demo ids. Server entities use UUIDv7. Router paths accept both; the API rejects non-UUID ids except the fixed `sample_…` ids. |
| Production may silently default to demo (Phase 1.5 open decision) | Approved decision: production builds must set `VITE_OMNIORA_SERVICE_MODE` explicitly; only development defaults to demo. |
| Runtime Google Fonts dependency | Geist and Geist Mono are licensed under the SIL Open Font License 1.1, which permits redistribution and self-hosting. Bundle them via `@fontsource-variable/*` (OFL text ships in the package) and remove the Google Fonts links. |

## 1. Backend layout (`backend/`)

```
backend/
  pyproject.toml          deps; pytest config
  alembic.ini, migrations/ versioned schema (0001_initial)
  .env.example
  src/omniora_api/
    config.py             Settings (pydantic-settings), validated; production guards
    app.py                create_app(): middleware, routers, error handlers
    errors.py             ApiError(code, message, details) + handlers → {"error": {...}}
    ids.py                UUIDv7 (RFC 9562)
    logging.py            JSON logs with key-based redaction
    db/                   engine/session factory, ORM models
    domain/               pure rules: projects (mirror of src/domain/projects/rules.ts), runs (state machine), plans (plan schema + graph validation)
    repositories/         SQL only: users, sessions, projects, runs (events, tasks, approvals, attempts, jobs), audit
    services/             use cases with transaction boundaries: auth, projects, runs
    api/                  routes + transport schemas + dependencies (session auth, CSRF, rate limits)
    llm/                  provider-independent interface, Anthropic adapter, unconfigured provider, router
    agents/project_manager.py   prompt, output schema, validation, bounded attempts
    worker/               job claim/lease loop, handlers, `python -m omniora_api.worker`
    security/             password hashing (Argon2id), session tokens, CSRF/Origin checks, rate limiting
    audit.py              hash-chained audit log
  tests/                  pytest; real PostgreSQL via OMNIORA_TEST_DATABASE_URL
    evals/                planning evaluation fixtures + deterministic graders
```

Rules: HTTP handlers call services, services own transactions and call repositories and domain functions,
repositories contain SQL only, the worker calls services, and agents call the `llm` interface. Domain modules
import nothing from FastAPI, SQLAlchemy, or providers.

## 2. API

All JSON, under `/api/v1`. Errors use `{"error": {"code", "message", "details"?}}` with codes from
`src/domain/errors.ts`. The request body limit is 64 KiB (413 above it).

### 2.1 Auth (BACKEND_CONTRACTS §3)

`POST /auth/register`, `POST /auth/sign-in`, `POST /auth/sign-out`, `GET /auth/me`,
`POST /auth/password-reset`.

- Passwords are hashed with Argon2id.
- The session token is 32 random bytes in an `HttpOnly; SameSite=Lax; Path=/` cookie (plus `Secure` in
  production). Only its SHA-256 hash is stored, and sessions expire after 14 days.
- Sign-out revokes the session server-side.
- Password reset returns `503 provider-not-configured`, because no email delivery exists. It does not pretend
  to send mail.
- **CSRF:** unsafe methods require the header `X-Omniora-Client: web`, and an `Origin` header (when present)
  must be in `OMNIORA_CORS_ORIGINS`. Browsers cannot send that custom header cross-origin without a preflight,
  and CORS rejects the preflight.
- Login attempts are rate-limited per email and IP (in-process limiter; limitation documented).

### 2.2 Projects (BACKEND_CONTRACTS §2)

Authenticated. Per-project authorization means another user's project returns `404`, so its existence is not
disclosed. `GET /projects?cursor&limit` is ordered by `(updated_at DESC, id DESC)` with an opaque keyset cursor.
`GET /projects/samples` is public and serves fixed fixtures.

### 2.3 Runs (BACKEND_CONTRACTS §5, extended)

| Method | Path | Behaviour |
| --- | --- | --- |
| POST | `/projects/{id}/runs` | Header `Idempotency-Key` (required). Starts a Project Manager planning run, returning `202 Run`; the same key returns the same run. `409 conflict` if another run is active. `503 provider-not-configured` if no model provider is configured. `429` above the per-user hourly limit. |
| GET | `/projects/{id}/runs` | Runs for the project, newest first |
| GET | `/runs/{id}` | `RunDetail`: run, current plan (version, content), tasks, pending approval, attempt summaries |
| POST | `/runs/{id}/cancel` | Allowed from `queued`, `planning`, and `awaiting-approval`; idempotent if already cancelled |
| GET | `/runs/{id}/events` | SSE. Replays persisted events after `Last-Event-ID` (or `?after=`), then polls. Heartbeat every 15 s. Closes after a terminal state is delivered or after 5 minutes (the client reconnects). |
| GET | `/runs/{id}/approvals` | Approvals for the run |
| POST | `/runs/{id}/approvals/{approvalId}` | `{decision: approve\|reject\|revise, plan_version, comment?}`. Repeating the same decision is idempotent (200, unchanged). A different decision on a decided approval, or a `plan_version` that is not the approval's, returns `409`. `revise` requires a comment and queues a new planning attempt that produces the next plan version. |

## 3. Run state machine

```
queued ──► planning ──► awaiting-approval ──► approved   (terminal for Phase 2: nothing executes)
  │            │               │  └──────────► rejected  (terminal)
  │            │               └─ revise ────► queued    (new plan version)
  │            └──► failed (terminal: attempts or deliveries exhausted)
  └────────────┴───────────────┴──► cancelled (terminal)
```

Transitions are validated in `domain/runs.py` and applied with compare-and-set
(`UPDATE runs SET state=:to WHERE id=:id AND state=:from`). Each transition appends a `run_event` in the same
transaction. **No transition starts execution:** `approved` only records consent. Execution belongs to future
agents and future phases.

## 4. Database schema (migration 0001)

| Table | Key columns |
| --- | --- |
| `users` | `id uuid` (v7), `email` (unique on `lower(email)`), `name`, `password_hash`, `created_at` |
| `sessions` | `id`, `user_id`, `token_hash` (unique), `created_at`, `expires_at`, `revoked_at` |
| `projects` | `id`, `owner_id`, `status`, `configuration jsonb`, `created_at`, `updated_at`; index on `(owner_id, updated_at DESC, id DESC)` |
| `project_history` | `id`, `project_id`, `at`, `summary` |
| `project_notes` | `id`, `project_id`, `content`, `at` |
| `runs` | `id`, `project_id`, `created_by`, `agent_role`, `state`, `idempotency_key`, `current_plan_version`, `failure_code`, `failure_message`, `event_seq`, timestamps; unique `(project_id, idempotency_key)`; partial unique index on `project_id` where the state is active |
| `run_events` | `id bigserial`, `run_id`, `seq` (unique per run), `type`, `data jsonb`, `at` |
| `plan_versions` | `id`, `run_id`, `version` (unique per run), `content jsonb`, `attempt_id`, `created_at` |
| `engineering_tasks` | `id`, `run_id`, `plan_version`, `key` (unique per plan version), `title`, `description`, `acceptance_criteria jsonb`, `depends_on jsonb`, `suggested_agent`, `status` (`proposed`) |
| `approvals` | `id`, `run_id`, `plan_version`, `gate`, `status` (pending/approved/rejected/revision-requested/superseded/cancelled), `decided_by`, `decided_at`, `comment`; partial unique on `run_id` where pending |
| `agent_attempts` | `id`, `run_id`, `plan_version`, `attempt`, `outcome`, `provider`, `model`, token counts, `latency_ms`, `error_code`, `error_message`, `validation_errors jsonb`, `raw_output` (truncated), `prompt_sha256`, `created_at` |
| `jobs` | `id`, `run_id`, `kind`, `status` (queued/leased/done/failed/cancelled), `deliveries`, `max_deliveries`, `available_at`, `lease_owner`, `lease_expires_at`, `last_error`, `dedupe_key` (unique) |
| `audit_log` | `id bigserial`, `at`, `actor_type`, `actor_id`, `action`, `entity_type`, `entity_id`, `data jsonb`, `prev_hash`, `hash` |

Event ordering: appending an event locks the run row (`SELECT … FOR UPDATE`) and increments `runs.event_seq`.
Per-run `seq` values are therefore gap-free and committed in order, so SSE replay by `seq` is deterministic and
never skips an event committed late.

Audit integrity: each row's `hash = sha256(prev_hash ‖ canonical_json(row))`, appended under a transaction-scoped
advisory lock. `verify_audit_chain()` recomputes the chain, and tests tamper with a row to prove detection.

## 5. Worker lifecycle and delivery semantics

- Start with `python -m omniora_api.worker`. Any number of processes can run.
- **Claim:** `SELECT … FROM jobs WHERE (status='queued' AND available_at<=now) OR (status='leased' AND
  lease_expires_at<now) ORDER BY available_at FOR UPDATE SKIP LOCKED LIMIT 1`, then set `leased`, the owner,
  the expiry (`now + lease_seconds`), and `deliveries += 1`.
- **Delivery is at-least-once.** A crashed worker's lease expires and another worker reclaims the job. If
  `deliveries > max_deliveries` (default 3), the run fails with `worker-exhausted`.
- **Safe commit:** the handler writes its results in one transaction that first runs
  `UPDATE jobs SET status='done' WHERE id=:id AND lease_owner=:me AND status='leased'`. If zero rows change,
  the lease was lost and everything rolls back. Plan versions are additionally unique per run, so a duplicate
  delivery that still reached commit cannot create a second plan.
- **Cancellation:** if the run is no longer `planning` at commit time, the result is discarded.
- **Timeouts:** each model call has a provider timeout, and the lease (default 600 s) exceeds the whole attempt
  budget.
- **Not exactly-once:** model calls may be repeated after a crash, which costs money but cannot corrupt state.
  Every attempt is persisted.

## 6. Model interface

`ModelRequest(system, messages, output_schema, max_output_tokens, effort)` →
`ModelResponse(text, usage{input_tokens, output_tokens}, provider, model, stop_reason, request_id, latency_ms)`.
Failures raise `ModelError(kind)` with kinds `not-configured`, `auth`, `rate-limited`, `timeout`, `unavailable`,
`bad-request`, `refused`, and `truncated`. Messages are safe; provider bodies and keys are never included.

- **Anthropic adapter.** It uses the official `anthropic` SDK. The model is `claude-opus-5-5` by default and
  configurable. Structured output uses `output_config.format` with a JSON Schema. Effort is configurable
  (default `high`). Server-side refusal fallback (`fallbacks: "default"`) is on by default and configurable.
  The SDK timeout and transport retries come from settings.
- **Unconfigured provider.** Used when no API key is set. Starting a run returns `503 provider-not-configured`
  with instructions, and no response is ever fabricated.
- **Test double.** A scripted provider lives only in `tests/`.

## 7. Project Manager agent

- **Input:** the validated configuration, the notes, and an optional revision comment, embedded as clearly
  delimited data.
- **Output (`ProjectPlan`):** summary, requirements (`id`, statement, kind, priority, source), assumptions, open
  questions (`id`, question, why, blocking), `recommended_stack` (required if and only if the stack mode is
  `recommend`), tasks (`key`, title, description, acceptance criteria, `depends_on`, `requirement_ids`,
  `suggested_agent` drawn from Agents 2–10), and required approvals (which must include `plan`).
- **Validation beyond the schema:**
  - unique keys;
  - every dependency resolves to an existing task;
  - no self-dependencies and no cycles (Kahn's algorithm);
  - every requirement is covered by at least one task, and every requirement reference resolves;
  - the recommended stack passes the same compatibility rules as the frontend;
  - size bounds hold.
- **Attempts:** up to `OMNIORA_PM_MAX_ATTEMPTS` (default 3). Each invalid output is fed back with the
  validation errors, and every attempt is persisted with its outcome.
- **Never:** write files, run commands, or invoke other agents. Proposed tasks are stored with status
  `proposed`.

## 8. Security boundaries

| Area | Boundary |
| --- | --- |
| Authentication | Server-side sessions with HttpOnly cookies; Argon2id; no user-supplied identity is trusted |
| Authorization | Every project and run query is scoped by `owner_id`; anything foreign returns 404 |
| CORS | Explicit origin allow-list with credentials; `*` is rejected in production |
| Input | Pydantic models with field limits; body size limit; UUID path validation |
| Rate limits | Run creation: per-user hourly limit from the database (multi-process safe). Sign-in: per-process limiter |
| Secrets | Read from the environment only; redacted from logs; never in responses; the frontend never sees them |
| Errors | Safe messages only; stack traces are logged, never returned |
| Production | `OMNIORA_ENV=production` requires secure cookies, an explicit CORS list, a non-default database URL, and `debug=false` |
| Health | `/health/live` checks the process; `/health/ready` checks database connectivity and that migrations are at head |

## 9. Migration sequence

1. `0001_initial`: all tables in §4.
2. Future changes go in new revisions only. Applied revisions are never edited.

Validation: `alembic upgrade head`, then `alembic downgrade base`, then `upgrade head` again, run in tests
against PostgreSQL, plus an autogenerate check that the ORM matches the migrations.

## 10. Frontend integration

- `src/domain/runs/run.ts`: Zod schemas for runs, events, plans, tasks, and approvals.
- `services/contracts/run-service.ts`: the `RunService` interface.
- `services/http/`: shared client (credentials, CSRF header, response validation, error mapping), plus HTTP
  project, auth, and run adapters. SSE runs through `EventSource` with `withCredentials`.
- Demo mode: `RunService` is "unavailable", and the UI explains that runs need API mode. API mode wires the HTTP
  adapters; unreachable APIs produce `network` errors with retry.
- Workspace: a new **Plan** tab (run status, plan, tasks with dependencies, open questions, approve, revise, and
  reject), and an agent panel showing persisted run events live.

## 11. Acceptance tests

| Area | Tests |
| --- | --- |
| Projects API | CRUD, rule parity with the frontend, pagination order, samples read-only, cross-user 404 |
| Contract | The frontend `describeProjectServiceContract` runs against the HTTP adapter and a mocked fetch reproducing API responses. The backend tests the same behaviours against PostgreSQL. |
| State machine | Every allowed and forbidden transition; compare-and-set races |
| Worker | Interruption (expired lease reclaimed), duplicate delivery (lost-lease commit rejected), exhausted deliveries, cancellation mid-run |
| Model | Invalid JSON, schema violation, cycle, unresolved dependency, retries then success, retries exhausted, provider errors mapped safely, unconfigured provider |
| Approvals | Approve, reject, revise produces version 2, stale version rejected, duplicate approval idempotent, conflicting decision rejected, unauthenticated or foreign user rejected |
| SSE | Replay after `Last-Event-ID`, deterministic order, terminal close |
| Auth | Register, sign-in, sign-out, session expiry, CSRF header and Origin enforcement, sign-in rate limit |
| Evaluation | Seven fixtures (§12) graded deterministically |
| Frontend | HTTP adapter error mapping, run UI states, approval flow, demo-mode messaging |

## 12. Evaluation fixtures

`backend/tests/evals/fixtures/*.json` hold an input, a candidate output, and expectations. The candidates are
**hand-authored reference plans, not recorded model outputs**: no provider credentials are available in this
environment, and fabricating "model" results would be dishonest. The graders are deterministic (structural
validity, requirement coverage, dependency correctness, and required question topics) and run in CI.
`python -m omniora_api.evals --live` runs the same graders against a real provider when credentials exist,
which costs money and must be run deliberately.

Fixtures: e-commerce website, Flutter mobile app, full-stack SaaS, incomplete requirements (must raise blocking
questions), conflicting technology preferences (must raise the conflict), invalid model output (must be
rejected), and cyclic dependencies (must be rejected).

## 13. Implementation status (end of Phase 2)

Implemented as planned, with these recorded deviations:

| Planned | Implemented | Why |
| --- | --- | --- |
| SSE only for events | SSE plus `GET /runs/{id}/events/history` (JSON) | The UI reconciles from persisted history; tests and tools can read events without a stream. |
| Login limiter "per email and IP" | Same, in-process | Documented limitation; a shared store is needed before running several API processes. |
| Requirement coverage for every requirement | Coverage is required for `must` requirements | `should`/`could` items may reasonably be deferred; the evaluation graders check the topics that matter. |
| Run state `awaiting-approval → queued` on revise | As planned; the old approval becomes `revision-requested`, and it is rejected for any later version | Stale approvals cannot approve newer plans. |

Verification and its limits are recorded in `docs/BACKEND.md` (Tests, Known limitations). In particular, no real
model provider was available, so the Anthropic adapter is verified against the installed SDK's signatures and a
fake client. The evaluation candidates are hand-authored reference plans.
