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
| `ANTHROPIC_API_KEY` / `GROQ_API_KEY` | none | Server-side only; only the selected provider's key is read. Without it, starting a planning run or a requirements session returns 503 `provider-not-configured`. |
| `OMNIORA_PM_MODEL` / `OMNIORA_PM_EFFORT` / `OMNIORA_PM_MAX_OUTPUT_TOKENS` | per provider: anthropic `claude-opus-5-5` / `high` / `16000`; groq `openai/gpt-oss-120b` / `medium` / `6000` | Model, reasoning effort, and output budget for the Project Manager. Unset values use the provider defaults. |
| `OMNIORA_PM_MAX_ATTEMPTS` | `3` | Model attempts per plan version (invalid output or transient errors each use one). |
| `OMNIORA_ANALYST_MAX_OUTPUT_TOKENS` / `OMNIORA_ANALYST_REQUEST_TOKEN_BUDGET` | per provider: anthropic `8000` / `150000`; groq `5000` / `7600` | Requirements Analyst output budget, and the most one request may use (estimated prompt + schema + output). A turn whose prompt would not fit fails with `context-too-large` instead of calling the provider. The analyst uses the same provider, model, and effort as planning. |
| `OMNIORA_ANALYST_MAX_ATTEMPTS` / `OMNIORA_ANALYST_MAX_TURNS` | `3` / `8` | Model attempts per discovery turn, and question turns per session (revision turns after "request changes" are not capped). |
| `OMNIORA_ANALYST_TURNS_PER_USER_PER_HOUR` | `30` | Database-backed limit on analyst turns. |
| `OMNIORA_ANTHROPIC_REFUSAL_FALLBACK` | `true` | Server-side refusal fallback (`fallbacks: "default"`); set `false` to disable. |
| `OMNIORA_RUNS_PER_USER_PER_HOUR` | `10` | Database-backed limit on starting runs (planning runs and requirements sessions together). |
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

| Revision | Adds |
| --- | --- |
| `0001` | Users, sessions, projects, runs, events, jobs, attempts, plans, tasks, approvals, and the append-only audit log. |
| `0002` | Requirements Analyst: run states `discovering`, `ready-for-review`, `needs-changes`; an `agent_role` check; `discovery_turns` (at most one queued or running turn per session), `discovery_questions`, `discovery_answers` (append-only history, idempotent per submission), `requirements_versions` (a trigger rejects any change to a version's content and makes the freeze and approval stamps write-once); and `runs.pinned_requirements_version_id` / `runs.requirements_skipped` for planning runs. The downgrade refuses to run while requirements sessions exist rather than deleting them. |

## Tests

The suite needs a **real PostgreSQL** database that it may wipe:

```bash
export OMNIORA_TEST_DATABASE_URL=postgresql://postgres@localhost:5432/omniora_test
pytest                         # everything (database tests are skipped, and reported, without the variable)
pytest tests/test_runs.py      # durable runs: worker recovery, duplicate delivery, approvals, SSE
pytest tests/test_requirements_domain.py tests/test_requirements_analyst.py   # Agent 2 contract and agent loop (no database)
pytest tests/test_requirements_api.py   # Agent 2 sessions, concurrency, recovery, approval, handoff (PostgreSQL)
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
  despite strict mode) is retried as an invalid output; when its message says the output ran out of completion
  tokens (gpt-oss reasoning counts toward them), it is reported as `truncated` instead. Groq's
  `failed_generation` (the rejected model output) is kept on the attempt for diagnosis. No path produces a plan without a real, validated model
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

## Requirements Analyst (Agent 2)

Agent 2 turns the brief, notes, and the user's answers into a versioned, structured requirements document that the
user approves before planning. It runs behind the same model interface, provider, and model as the Project
Manager, and has no tools.

**A session is a run** with `agent_role = "requirements-analyst"`. It reuses the run row lock, event stream
(`GET /runs/{id}/events`), jobs and leases, attempts, approvals, and the audit chain. Planning and discovery
share the one-active-run-per-project rule.

```
queued → discovering ⇄ ready-for-review → awaiting-approval → approved
                ↑                                  │
                └──────── needs-changes ←──────────┘   (request changes, with a comment)
cancelled from any active state; failed is reserved for terminal problems
```

Transient progress is the latest **turn**'s status (`queued`, `running`, `completed`, `failed`, `cancelled`),
not a run state. A failed turn never fails the session: every answer is kept, and `POST …/turns/retry` re-queues
the same turn.

**One turn** (`requirements-turn` job, `worker/discovery.py`):

1. The worker locks the run, moves it to `discovering`, marks the turn `running`, and builds a compact,
   authoritative summary: the brief, numbered notes, the current version (or the project's last approved
   version, so ids stay stable across sessions), and every question with its latest answer. It does not resend
   a growing transcript.
2. The model returns questions (at most five), requirement operations (`add` / `update` / `deprecate`),
   assumptions, a readiness claim, and short decision notes. Up to `OMNIORA_ANALYST_MAX_ATTEMPTS` attempts, each
   persisted, with validation errors fed back.
3. `domain/requirements.py` validates the output against persisted state, then the server applies it: it
   assigns `REQ-` ids (never reused; nothing is deleted, only deprecated) and `DQ-` question keys, and builds the
   next version with a SHA-256 content hash and a parent reference.
4. The commit is lease-checked, as for planning. Unique `(run, version)` and `(run, question key)` constraints
   stop a re-delivered job from committing twice. If the version is ready, the session moves to
   `ready-for-review`.

**Deterministic rules** (an output breaking any of them is rejected and retried):

- No model-assigned ids; no unknown, duplicated, or deprecated targets.
- `source: answer` must cite `answer:DQ-…` of a question the user actually answered, never an "I don't know".
  `brief` and `note` sources must cite a real brief field or note number.
- Inferred requirements cannot have high confidence. An assumption that stands in for an "I don't know" answer
  must have low confidence.
- Lowering or deprecating a "must" needs a reason and evidence from the user's answer.
- No repeated questions; choice questions need 2–8 distinct options; none on the final turn.
- **Tenancy:** `multi` requires an active "must" requirement tagged `tenant-isolation` with acceptance criteria;
  `unknown` requires an open blocking question with topic `tenancy`.
- **Readiness** is recomputed: no unanswered blocking question, every blocking "I don't know" covered by a
  low-confidence assumption, tenancy known, at least one must-have. A false `ready` claim is rejected.

**Answers and approval.** Answers are append-only (the newest row is current) and validated against the question's
kind. Each submission has an `Idempotency-Key`; a replay applies nothing. Answers cannot change while a turn is
queued or running, and changing one after readiness reopens discovery, so a stale version can never be submitted.
`submit` freezes the latest ready version and opens a `requirements` approval. Approval stamps the version
(immutable from then on); "request changes" requires a comment and queues a revision turn.

**Handoff to Agent 1.** `POST /projects/{id}/runs` pins the project's latest approved version to the planning run
(`pinned_requirements_version_id`). The planning worker reloads that version, verifies its hash, and gives the
Project Manager the exact approved requirements. The plan then references their `REQ-` ids instead of restating
them; its own additions use `D1`, `D2`, … (source `inferred`). `plan_problems` rejects unknown or deprecated ids,
restated approved requirements, and any approved must-have that no task covers and that is not listed in
`flagged_requirements` with a reason. Without approved requirements, planning returns `409` unless the request
sets `withoutRequirements: true`. That choice is stored on the run (`requirements_skipped`) and shown in the UI.

### Requirements Analyst evaluation

`python -m omniora_api.evals --agent requirements` grades six stored fixtures (`evals/discovery_fixtures/`): a
vague brief, a multi-tenant SaaS, contradictory answers, a clear project, an "I don't know" answer to a critical
question, and a validator fixture (an invented answer). Each stores the persisted state a turn would see, and a
**hand-authored reference output, not model output**. Graders run the production validator, then structured
checks (readiness, tenancy, question counts and topics, how unknown answers were handled). The only text check is
that a tenant-isolation requirement's criteria express denial, against a keyword list fixed in the fixture.
Stored: 6/6. Add `--live` for real model calls, and `--fixture <name>` to re-check one scenario.

#### Live results: Groq `openai/gpt-oss-120b`, 2026-10-29

Effort `medium`, at most 3 attempts per fixture, through the production agent code (not the API or worker). Each
round is a single sample.

| Round | Analyst output budget | Fixtures | Passed all checks | Model calls | Tokens reported (in / out) |
| --- | --- | --- | --- | --- | --- |
| 1 | 3,000 | 5 | 2/5 (contradictory-answers, unknown-critical-answer) | 11 | 15,496 / 13,801 |
| 2 | 5,000 | multi-tenant-saas | 0/1 | 3 | none reported |
| 3 | 5,000, allowed tags listed in the prompt | multi-tenant-saas | 0/1 | 3 | 1,802 / 2,975 |

- **multi-tenant-saas never produced an accepted output.** In round 1, all three attempts were rejected by Groq's
  own schema check. One diagnostic call showed why: the hidden reasoning counts toward `max_completion_tokens`,
  and the 3,000-token budget ran out after about 700 visible tokens. Groq reports that as `json_validate_failed`.
  Fixes: the Groq analyst budget is now 5,000, and the adapter reports this case as `truncated`. In round 2, Groq
  still rejected all three attempts, now as a real schema mismatch. The truncated output had also used a tag
  outside the allowed list (`payment`), so the prompt now lists the allowed tags. In round 3, one attempt produced
  a complete output, which our validator rejected because an inferred requirement claimed high confidence. The
  other two were still rejected by Groq. **The cause of those remaining rejections is not confirmed.** The adapter
  now keeps Groq's `failed_generation` on the attempt, and the analyst feeds its own validation of that output
  back on the next attempt, so the next live run can be diagnosed.
- **vague-brief (failed):** the output was valid, but the analyst asked only a blocking tenancy question, not
  about users or core features, and put guessed personas into low-confidence assumptions. The prompt now says
  the tenancy question comes in addition to, not instead of, the questions about users and features. That has
  not been re-verified live.
- **clear-project (failed):** the output was valid, but the analyst asked a blocking question about deployment
  and so did not declare readiness, while the fixture expects no blocking questions. Left failing; the grader was
  not changed.
- **Validator catches in live output** (each rejected and retried): evidence `inferred` used as a citation;
  withdrawing questions that were already answered; re-asking a question the user had answered "I don't know";
  an inferred requirement with high confidence.
- **Usage:** 18 live calls in total (17 evaluation calls plus 1 diagnostic call), with 17.3K input and 16.8K
  output tokens reported. Nine calls rejected by Groq reported no usage, although they consumed quota. Latency
  per call was 2 to 37 s. No rate-limit errors occurred. Cost is not reported, because pricing depends on the
  account's plan.
- **Not run live:** the full API + worker + Groq path for discovery and planning from approved requirements. The
  day's token allowance was nearly used up. That path is verified with the scripted provider, against real
  PostgreSQL (`tests/test_requirements_api.py`) and in a real browser against the real API.

## Security boundaries

| Area | Implementation |
| --- | --- |
| Identity | Email and password accounts; Argon2id hashes; random 256-bit session tokens in `HttpOnly; SameSite=Lax` cookies (`Secure` in production); only SHA-256 digests stored; server-side revocation on sign-out; 14-day expiry. |
| Authorization | Every project, run, and requirements-session query is scoped to the owner; other users' resources return 404. |
| CSRF | State-changing requests need `X-Omniora-Client: web`; an `Origin` header, when present, must be allow-listed. |
| CORS | Explicit origins with credentials; `*` is rejected in production. |
| Input | Pydantic models with `extra="forbid"` and length limits, a 64 KiB body limit, UUID path validation, and domain rules mirrored from the frontend. |
| Abuse | Runs and analyst turns: per-user hourly limits from the database. Sign-in: per-IP+email sliding window (in-process). |
| Audit | Hash-chained `audit_log`; a database trigger rejects UPDATE and DELETE; `verify_audit_chain()` detects storage-level tampering. |
| Errors | `{"error": {"code", "message", "details"}}` with safe messages only; stack traces are logged, never returned. |
| Model | Credentials server-side only; project data and answers are wrapped as delimited data in the prompt; outputs are validated against persisted state before anything is stored; neither agent has tools. |

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
- **Requirements Analyst is not yet reliable live:** 2/5 evaluation fixtures pass on Groq, and the multi-tenant
  fixture has not produced an accepted output (see Requirements Analyst evaluation). Review the questions and
  requirements before approving; the approval gate exists for this reason.
- **Requirements Analyst limits.** The validator checks structure and evidence, not meaning: it cannot tell
  whether a question is a paraphrase of one already answered (only exact repeats are rejected), or whether a
  tenant-isolation criterion really proves denial (the evaluation grader checks that wording; the validator only
  requires the tag, priority, and criteria). Token counts for the request budget are estimated (characters ÷ 3),
  not measured. A session is capped at `OMNIORA_ANALYST_MAX_TURNS` question turns.
- **Cross-site deployments** (frontend and API on different registrable domains) are not supported by the
  `SameSite=Lax` cookie.
- The health check reads migrations from the source tree, so the API must run from a checkout or an editable
  install.
