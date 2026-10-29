# Omniora backend

A FastAPI service (`backend/`) that provides accounts, project persistence, durable agent runs, and
**Agent 1, the Project Manager**. It plans; it never writes files, runs commands, executes code,
deploys, or starts other agents. Design rationale: [PHASE_2_IMPLEMENTATION_PLAN.md](PHASE_2_IMPLEMENTATION_PLAN.md).
HTTP contract: [BACKEND_CONTRACTS.md](BACKEND_CONTRACTS.md).

## Requirements

- Python 3.12 (`uv python install 3.12` or python.org)
- PostgreSQL 14+ (developed and tested against PostgreSQL 16.2)
- Optional: an Anthropic or Groq API key, required only to run the Project Manager agent

## Setup

```bash
cd backend
python3.12 -m venv .venv            # or: uv venv --python 3.12 .venv
.venv/Scripts/activate              # Windows; on macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                # then edit OMNIORA_DATABASE_URL (and ANTHROPIC_API_KEY if planning)
createdb omniora                    # or create the database another way
alembic upgrade head                # apply migrations
```

## Run

Run the API and at least one worker. Both read the same environment.

```bash
uvicorn omniora_api.app:app --port 8000          # API at http://localhost:8000 (docs at /api/docs outside production)
python -m omniora_api.worker                      # worker; start several for throughput or redundancy
```

Then run the frontend in API mode from the repository root:

```bash
VITE_OMNIORA_SERVICE_MODE=api VITE_OMNIORA_API_BASE_URL=http://localhost:8000 npm run dev
```

The frontend and API must be **same-site** (for example both on `localhost`, or `app.example.com` and
`api.example.com`), because the session cookie is `SameSite=Lax`. `localhost` and `127.0.0.1` are different
sites. Behind a reverse proxy, start uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy ip>` so client
IPs (used for sign-in rate limiting) are correct.

## Configuration

All settings are environment variables, validated at startup by `omniora_api/config.py` (see
`backend/.env.example`). Highlights:

| Variable | Default | Notes |
| --- | --- | --- |
| `OMNIORA_ENV` | `development` | `production` requires `OMNIORA_COOKIE_SECURE` (defaults to true there) and explicit https CORS origins, and disables `/api/docs`. |
| `OMNIORA_DATABASE_URL` | none (required) | PostgreSQL only; other databases are rejected. |
| `OMNIORA_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated. Also used for the Origin check on state-changing requests. |
| `OMNIORA_MODEL_PROVIDER` | `anthropic` | `anthropic` or `groq`. Chosen explicitly: a key for another provider never switches providers. |
| `ANTHROPIC_API_KEY` / `GROQ_API_KEY` | none | Server-side only; only the selected provider's key is read. Without it, `POST /projects/{id}/runs` returns 503 `provider-not-configured`. |
| `OMNIORA_PM_MODEL` / `OMNIORA_PM_EFFORT` / `OMNIORA_PM_MAX_OUTPUT_TOKENS` | per provider: anthropic `claude-opus-5-5` / `high` / `16000`; groq `openai/gpt-oss-120b` / `medium` / `6000` | Model, reasoning effort, and output budget for the Project Manager. Unset values use the provider defaults. |
| `OMNIORA_PM_MAX_ATTEMPTS` | `3` | Model attempts per plan version (invalid output or transient errors each use one). |
| `OMNIORA_ANTHROPIC_REFUSAL_FALLBACK` | `true` | Server-side refusal fallback (`fallbacks: "default"`); set `false` to disable. |
| `OMNIORA_RUNS_PER_USER_PER_HOUR` | `10` | Database-backed limit on starting runs. |
| `OMNIORA_WORKER_LEASE_SECONDS` / `OMNIORA_JOB_MAX_DELIVERIES` | `60` / `3` | Crash recovery window and redelivery bound. |

Secrets are `SecretStr` values, never logged, and never returned by the API. Logs are JSON with key-based
redaction (`password`, `token`, `cookie`, `api_key`, and similar) and provider-key pattern scrubbing.

## Migrations

```bash
alembic upgrade head          # apply
alembic downgrade -1          # roll back one revision
alembic check                 # fails if the ORM models and migrations disagree
alembic revision --autogenerate -m "describe change"   # then review the generated file by hand
```

Applied revisions are never edited; every change gets a new revision. `GET /health/ready` reports 503 until the
database is at the migration head.

## Tests

The suite needs a **real PostgreSQL** database that it may wipe:

```bash
export OMNIORA_TEST_DATABASE_URL=postgresql://postgres@localhost:5432/omniora_test
pytest                         # everything (database tests are skipped, and reported, without the variable)
pytest tests/test_runs.py      # durable runs: worker recovery, duplicate delivery, approvals, SSE
ruff check src tests migrations && ruff format --check src tests migrations
pip-audit                      # dependency advisories
```

No test calls a real model. Provider behaviour is tested with a fake SDK client and a scripted provider that
exists only under `tests/`.

## Using Groq

The Project Manager can run on Groq through the official `groq` SDK (`llm/groq_provider.py`), behind the same
interface as the Anthropic adapter. To enable it, add to `backend/.env` (git-ignored; never commit it):

```bash
OMNIORA_MODEL_PROVIDER=groq
GROQ_API_KEY=<your Groq key>          # from https://console.groq.com/keys
# OMNIORA_PM_MODEL=openai/gpt-oss-120b   # default for groq; any model your key can access
```

Restart the API and the worker after changing it. `GET /health/ready` then reports
`"model_provider": "configured"` and `"model_provider_name": "groq"`.

How the adapter behaves:

- **Model:** `openai/gpt-oss-120b`, a production model on Groq with strict JSON-schema structured output and
  65,536 maximum completion tokens. Availability for the key was confirmed with Groq's models endpoint on
  2026-10-29.
- **Structured output:** strict `json_schema` on models Groq documents as strict-capable (gpt-oss-20b and 120b,
  qwen3.8-27b, muse-spark-open); best-effort schema on gpt-oss-safeguard-20b; JSON mode with the schema in the
  prompt otherwise. The agent's Pydantic and semantic validation runs regardless.
- **Reasoning:** gpt-oss uses `reasoning_effort` low/medium/high (Omniora's `xhigh` and `max` map to `high`).
  Reasoning text is excluded from responses (`include_reasoning=false`).
- **Limits:** on Groq's Developer tier, gpt-oss-120b allows 8K tokens per minute (including the requested
  completion budget) and 200K tokens per day. The default 6,000-token output budget fits. Raising
  `OMNIORA_PM_MAX_OUTPUT_TOKENS` past the per-minute limit makes every request fail with a clear, non-retried
  "exceeds Groq's per-minute token limit" error.
- **Failures:** the SDK retries connection errors, 408, 409, 429, and 5xx up to `OMNIORA_MODEL_TRANSPORT_RETRIES`
  (honouring `retry-after` up to 60 s). After that, a rate limit waits for `retry-after` (capped at 60 s) before
  the agent's next attempt. Authentication, permission, unknown-model, and oversized requests are permanent and
  not retried. Groq's occasional `json_validate_failed` (its own schema rejection, seen 2 times in 24 live calls
  despite strict mode) is retried as an invalid output. No path produces a plan without a real, validated model
  response.

## Planning evaluation

```bash
python -m omniora_api.evals          # grade the 7 stored fixtures (free, deterministic)
python -m omniora_api.evals --live   # generate fresh plans with the configured provider, then grade them (billed)
```

Fixtures live in `src/omniora_api/evals/fixtures/`. Their stored candidate outputs are **hand-authored reference
plans, not recorded model outputs**. Graders check structural validity, dependency correctness, requirement
coverage (keyword topics), and whether important questions were raised. There is no LLM judge. `--live` sends the
five planning fixtures through the production factory and agent; the two validator fixtures (invalid output,
cyclic dependencies) are reported as not applicable in live mode. Add `--out report.json` to save the full report,
including each accepted plan.

### Live results: Groq `openai/gpt-oss-120b`, 2026-10-29

Effort `medium`, 6,000 output tokens, at most 3 attempts per fixture. Every number below comes from real API
responses. Results vary between runs; each round is a single sample.

| Round | Change before the round | Plans accepted | Passed all checks | Model calls | Tokens (in / out) |
| --- | --- | --- | --- | --- | --- |
| 1 | none (Phase 2 prompt) | 4/5 | 2/5 | 12 | 14,102 / 34,357 |
| 2 | prompt states the stack-compatibility rules and that every task needs a requirement id | 5/5 | 2/5 | 5 | 6,800 / 18,775 |
| 3 | grader folds Unicode hyphens and accepts "log in" / "login" / "authentication"; prompt forbids inventing a product from a vague brief | 5/5 | **4/5** | 5 | 7,145 / 17,285 |

- **Round 1 failures, all caught by validation and retried:** 7 invalid outputs (tasks without requirement ids,
  React combined with Next.js, an uncovered must-have requirement) and 1 provider schema rejection.
  fullstack-saas exhausted its 3 attempts, so its run failed (`invalid-plan`) and no plan was accepted.
- **Dependency correctness:** every accepted plan in every round had an acyclic graph with resolvable references.
  The validator enforces this, so no plan with a broken graph can be accepted.
- **Grader fix in round 3:** evidence-based. The round-2 ecommerce plan required "register, log in, and log out"
  and had a "User Authentication Implementation" task, but the keyword list lacked those words and the model
  wrote U+2011 hyphens.
- **Prompt fix in round 3:** the round-2 incomplete-requirements plan invented a product (browse offerings, place
  orders, 12 build tasks) while also asking what the business does. In round 3 it planned discovery first and
  asked who the customers are and which features they need.
- **Still failing (genuine):** fullstack-saas has no requirement or task for isolating each workspace's data (it
  only asks about tenancy in an open question). It is left failing rather than tuned to the fixture.
- **Rate limits and timeouts:** none in the evaluation. Latency per call was 9-50 s.
- **Production path:** one run through the real API, durable run, worker, and PostgreSQL reached
  `awaiting-approval` with plan v1 (7 requirements, 4 open questions, 9 proposed tasks). Its first attempt hit a
  provider schema rejection and was retried.
- **Usage:** 24 live model calls in total (evaluation plus production-path check), about 29.5K input and 73.4K
  output tokens. That is well within the 200K tokens-per-day Developer limit. Cost is not reported, because pricing
  depends on the account's plan.

## How runs work

1. `POST /projects/{id}/runs` with an `Idempotency-Key` creates a `queued` run and a `plan` job in one
   transaction. Repeating the key returns the same run.
2. A worker claims the job (`SELECT … FOR UPDATE SKIP LOCKED`), leases it, and renews the lease in the
   background.
3. The worker moves the run to `planning` and calls the model up to `OMNIORA_PM_MAX_ATTEMPTS` times. Each
   attempt is validated: shape with Pydantic, then semantics (unique ids, resolvable dependencies, an acyclic
   graph, must-have coverage, stack rules, a `plan` approval gate). Each attempt is persisted.
4. The final transaction commits only if the worker still holds its lease. It stores the plan version and
   proposed tasks, opens a pending approval, and moves the run to `awaiting-approval`.
5. The user approves, rejects, or requests a revision **for that exact plan version**. A revision queues plan
   v2; the v1 approval is closed and can no longer approve anything.

**Delivery semantics: at-least-once.** If a worker dies, its lease expires and another worker re-delivers the
job; after `OMNIORA_JOB_MAX_DELIVERIES` deliveries the run fails with `worker-exhausted`. Results commit only
under a valid lease, and plan versions are unique per run, so duplicate delivery cannot create two plans. Model
calls may repeat after a crash, which costs money but cannot corrupt state. Execution is **not exactly-once**.

**Events.** Every state change appends a run event in the same transaction, under the run's row lock, so
per-run sequence numbers are gap-free and committed in order. `GET /runs/{id}/events` (SSE) replays from
`Last-Event-ID` and then polls the database every second. `GET /runs/{id}/events/history?after=N` returns the
same events as JSON.

## Security boundaries

| Area | Implementation |
| --- | --- |
| Identity | Email and password accounts; Argon2id hashes; random 256-bit session tokens in `HttpOnly; SameSite=Lax` cookies (`Secure` in production); only SHA-256 digests stored; server-side revocation on sign-out; 14-day expiry. |
| Authorization | Every project and run query is scoped to the owner; other users' resources return 404. |
| CSRF | State-changing requests need `X-Omniora-Client: web`; an `Origin` header, when present, must be allow-listed. |
| CORS | Explicit origins with credentials; `*` is rejected in production. |
| Input | Pydantic models with `extra="forbid"` and length limits, a 64 KiB body limit, UUID path validation, and domain rules mirrored from the frontend. |
| Abuse | Runs: per-user hourly limit from the database. Sign-in: per-IP+email sliding window (in-process). |
| Audit | Hash-chained `audit_log`; a database trigger rejects UPDATE and DELETE; `verify_audit_chain()` detects storage-level tampering. |
| Errors | `{"error": {"code", "message", "details"}}` with safe messages only; stack traces are logged, never returned. |
| Model | Credentials server-side only; project data is wrapped as delimited data in the prompt; outputs are validated before persistence; the agent has no tools. |

## Known limitations

- **No email:** no verification and no password reset (the endpoint honestly returns 503). MFA and account
  lockout are not implemented. All three are needed before a public launch.
- **Sign-in rate limiting is per process.** Use a shared store (or the database) before running several API
  processes.
- **SSE polls PostgreSQL** (default 1 s per open stream). Adequate at current scale; switch to `LISTEN/NOTIFY`
  or a broker before high fan-out.
- **Live validation covers Groq only.** The Project Manager has been validated against Groq
  `openai/gpt-oss-120b` (see Planning evaluation). The Anthropic adapter is still verified only against the SDK's
  signatures and a fake client.
- **Plan quality is good, not perfect:** in the latest live round, 4/5 evaluation fixtures pass every check. Read
  the plan before approving it; the approval gate exists for this reason.
- **Cross-site deployments** (frontend and API on different registrable domains) are not supported by the
  `SameSite=Lax` cookie.
- The health check reads migrations from the source tree, so the API must run from a checkout or an editable
  install.
