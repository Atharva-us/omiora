# Backend contracts

Status: **§2 Projects, §3 Authentication, and §5 Runs are implemented** in `backend/` (Phase 2; see
[BACKEND.md](BACKEND.md)) and verified by backend tests against PostgreSQL. The frontend's ProjectService contract
suite also passes through the HTTP adapter against a running API. §4 and §6–9 remain **design drafts**: nothing in
them exists. Frontend interfaces live in `src/services/contracts/`; shapes are Zod schemas in `src/domain/` and
Pydantic models in `backend/src/omniora_api/`.

Conventions:

- JSON over HTTPS, `/api/v1` prefix, ISO-8601 UTC timestamps, cursor pagination (`?cursor=&limit=`).
- **Identifiers are server-generated UUIDv7** and treated as opaque strings by clients. The demo adapter's local
  `prj_…` ids are client-side demo ids only; the API rejects them (404). The fixed `sample_…` ids are read-only.
- JSON field names are camelCase.
- All `/api/v1` endpoints except `GET /projects/samples` require the session cookie. State-changing requests
  also need the header `X-Omniora-Client: web`, and an allow-listed `Origin` when the browser sends one.
- Errors are `{ "error": { "code": AppErrorCode, "message": string, "details"?: string[] } }`, where `code` is one of
  `src/domain/errors.ts` `APP_ERROR_CODES`: `validation` (422, or 413 for oversized bodies), `not-found` (404),
  `read-only` (403), `forbidden` (403), `unauthenticated` (401), `invalid-credentials` (401), `email-in-use` (409),
  `conflict` (409), `rate-limited` (429, with `Retry-After`), `provider-not-configured` (503), and
  `network`/`unexpected` (5xx). Another user's resource is reported as `not-found`, so its existence is not disclosed. `message` and `details` must be
  safe to show to end users; stack traces and internals never leave the server.
- The HTTP adapter validates every response body with the domain schemas before returning it to the UI.
- Long-running work returns `202 Accepted` with a resource to poll, plus a server-sent events stream for live
  updates.

## 1. Service boundaries and their backends

| Frontend boundary                  | Phase 1 implementation                 | Needed backend                     |
| ---------------------------------- | -------------------------------------- | ---------------------------------- |
| `ProjectService`                   | demo: localStorage; **api: `services/http/project-service.ts`** | Projects API (section 2), **implemented** |
| `AuthenticationService`            | demo: always rejects; **api: `services/http/authentication-service.ts`** | Auth API (section 3), **implemented** |
| `RunService`                       | demo: unavailable; **api: `services/http/run-service.ts`** | Runs API (section 5), **implemented** for the Project Manager |
| `ProjectPlanningService`, `RequirementsAnalysisService`, `ReferenceAnalysisService` | none | Planning API (section 4) |
| `ModelRoutingService`, `AgentOrchestrationService` | none | Runs API (section 5)         |
| `FileOperationsService`            | none                                   | Files API (section 6)              |
| `SandboxExecutionService`, `BrowserAutomationService` | none                | Internal sandbox workers (section 7) |
| `BuildExecutionService`, `AutomatedTestingService`, `CodeRepairService` | none | Builds/Tests API (section 8) |
| `PackagingService`, `DeploymentService` | none                              | Export/Deploy API (section 9)      |

## 2. Projects

| Method | Path                               | Body / response                                       |
| ------ | ---------------------------------- | ----------------------------------------------------- |
| GET    | `/projects?limit=&cursor=`         | → `{ items: Project[], nextCursor }` (owner's only; ordered by `updatedAt` desc, then id desc; `limit` ≤ 100) |
| GET    | `/projects/samples`                | → `Project[]` (`source: "sample"`)                    |
| POST   | `/projects`                        | `ProjectConfiguration` → `201 Project` (`status: "configured"`) |
| GET    | `/projects/{id}`                   | → `Project` / `404`                                   |
| PATCH  | `/projects/{id}`                   | `{ name?, configuration? }` → `Project`               |
| DELETE | `/projects/{id}`                   | → `204`                                               |
| GET    | `/projects/{id}/history`           | → `ProjectHistoryEntry[]` (newest first; `[]` for samples) |
| GET    | `/projects/{id}/notes`             | → `ProjectNote[]` (oldest first)                      |
| POST   | `/projects/{id}/notes`             | `{ content }` → `201 ProjectNote`                     |

`Project` is `{ id, source, status, configuration, createdAt, updatedAt }`. The name and stack live only in
`configuration`. `configuration.stack` is a discriminated union: `{ "mode": "recommend" }` or
`{ "mode": "custom", "technologies": TechnologyId[] }`.

The server enforces the same rules as `src/domain/projects/rules.ts` (`PROJECT_LIMITS`,
`validateProjectConfiguration`, `validateNoteContent`) and normalises input the same way
(`normalizeConfiguration`). Client validation is for UX only. The executable behavioural contract is
`src/test/contracts/project-service.contract.ts`: the HTTP adapter must pass it against a test server.

## 3. Authentication

Prefer a hosted identity provider or backend-issued **HttpOnly, Secure, SameSite** session cookies. The SPA never
stores tokens in JavaScript-readable storage.

| Method | Path                    | Body → response                          |
| ------ | ----------------------- | ---------------------------------------- |
| POST   | `/auth/register`        | `{ name, email, password }` → `AuthUser` + session cookie |
| POST   | `/auth/sign-in`         | `{ email, password }` → `AuthUser` + session cookie |
| POST   | `/auth/sign-out`        | → `204`                                  |
| GET    | `/auth/me`              | → `AuthUser` / `401`                     |
| POST   | `/auth/password-reset`  | `{ email }` → **503 `provider-not-configured`** until email delivery exists. When implemented it must answer identically whether or not the account exists. |

Implemented: Argon2id password hashes; a random session token in an `HttpOnly; SameSite=Lax` cookie (`Secure` in
production) whose SHA-256 digest is stored; server-side revocation; a 14-day expiry; sign-in rate limiting; and the
CSRF header plus Origin check.

## 4. Planning and analysis (draft; superseded for planning by §5)

| Method | Path                                | Notes                                         |
| ------ | ----------------------------------- | --------------------------------------------- |
| POST   | `/projects/{id}/plan`               | → `202`, then `ProjectPlan`                   |
| POST   | `/projects/{id}/plan/revisions`     | `{ feedback }` → `ProjectPlan`                |
| POST   | `/projects/{id}/requirements/analyse` | → `AnalysedRequirement[]`                   |
| POST   | `/references/analyse`               | `{ url }` → `ReferenceAnalysis`. The fetch runs in a sandboxed browser with SSRF protection (block private IP ranges and metadata endpoints). Design language is extracted; assets are never copied. |

## 5. Runs (model routing and agent orchestration)

| Method | Path                         | Notes                                              |
| ------ | ---------------------------- | -------------------------------------------------- |
| POST   | `/projects/{id}/runs`        | Header `Idempotency-Key` (8–100 chars, required); optional body `{ withoutRequirements: true }` → `202 Run`; the same key again → `200` with the same run. The run is pinned to the project's latest approved requirements (`pinnedRequirementsVersionId`). With no approved requirements and no `withoutRequirements`, `409 conflict`; the explicit skip is recorded (`requirementsSkipped: true`). `409 conflict` also if a run or requirements session is already active; `503 provider-not-configured`; `429 rate-limited`; `403 read-only` for samples. |
| GET    | `/projects/{id}/runs`        | → `Run[]` (planning runs only, newest first)       |
| GET    | `/runs/{runId}`              | → `RunDetail { run, plan, tasks, approvals, attempts, requirements }`; `requirements` is the pinned version `{ versionId, sessionId, version, contentSha256 }` or null. `plan.content.flaggedRequirements` lists approved must-haves left uncovered, with reasons. |
| POST   | `/runs/{runId}/cancel`       | → `Run`. Allowed from `queued`, `planning`, or `awaiting-approval`; idempotent once cancelled; `409` from other terminal states. |
| GET    | `/runs/{runId}/events`       | SSE. `id` = per-run sequence number; resumes after `Last-Event-ID` (or `?after=`); `event: end` after a terminal state; heartbeats; closes after 5 minutes (clients reconnect). |
| GET    | `/runs/{runId}/events/history?after=` | → `RunEvent[]` as JSON (same data, for reconciliation) |
| GET    | `/runs/{runId}/approvals`    | → `Approval[]`                                      |
| POST   | `/runs/{runId}/approvals/{approvalId}` | `{ decision: "approve" \| "reject" \| "revise", planVersion, comment? }` → `Approval`. The same decision again → `200` unchanged. A different decision, a wrong `planVersion`, or a superseded approval → `409`. `revise` requires `comment` and queues the next plan version. |

Run states: `queued → planning → awaiting-approval → approved | rejected`, plus `revise → queued`, and
`failed` / `cancelled`. **`approved` records consent only; nothing executes in this phase.** `RunDetail.tasks` are
the plan's proposed tasks (`status: "proposed"`, never "done").

Runs are durable: state lives in the database, and workers resume from it. While a run waits for a human decision
its state is `awaiting-approval`. Events are append-only, and each carries a monotonically increasing id so the
UI can resume a dropped stream. Model routing (`ModelRoutingService`) is internal to the backend. Provider API
keys stay server-side. See `docs/ARCHITECTURE.md` §8 for orchestration, retry, cancellation, and audit
requirements.

## 5.1 Requirements sessions (Agent 2)

A session id is a run id: progress uses `GET /runs/{id}/events` and `/events/history` from §5. All writes need
the CSRF header and Origin check; other users' sessions return `404`.

| Method | Path | Notes |
| ------ | ---- | ----- |
| POST | `/projects/{id}/requirements-sessions` | Header `Idempotency-Key` → `202 RequirementsSession`; same key → `200`. `409` if a run or session is active; `503`; `429`; `403 read-only` for samples. |
| GET | `/projects/{id}/requirements-sessions` | → `RequirementsSession[]` (newest first) |
| GET | `/requirements-sessions/{id}` | → `SessionDetail { session, turn, maxTurns, questions (each with its current answer), version, approvals, attempts }` |
| POST | `/requirements-sessions/{id}/answers` | Header `Idempotency-Key`; `{ answers: [{ questionKey, value?, unknown? }] (≤ 20), advance }` → `SessionDetail`. Values are validated per question kind (one offered option, a non-empty subset of options, a boolean, or 1–2000 characters); `unknown: true` takes no value. A replayed key applies nothing. `409` while a turn is queued or running, or (with `advance`) after a failed turn: retry it instead. |
| POST | `/requirements-sessions/{id}/turns/retry` | → `SessionDetail`. Re-queues a failed turn; idempotent while it is queued or running. |
| POST | `/requirements-sessions/{id}/submit` | `{ version }` → `SessionDetail`. Only from `ready-for-review` and only the latest version; freezes it and opens a `requirements` approval. Idempotent. |
| POST | `/requirements-sessions/{id}/approvals/{approvalId}` | `{ decision: "approve" \| "request-changes", version, comment? }` → `SessionDetail`. `request-changes` needs a comment and queues a revision turn. Same decision twice → unchanged; stale version → `409`. |
| POST | `/requirements-sessions/{id}/cancel` | → `SessionDetail`; idempotent. |
| GET | `/requirements-sessions/{id}/versions` | → `VersionSummary[]` |
| GET | `/requirements-sessions/{id}/versions/{n}?diff={m}` | → `RequirementsVersion` (content, hash, parent, freeze and approval stamps), with `diff { fromVersion, added, deprecated, changed[{id, fields}], contextFields }` when `diff` is given. |
| GET | `/projects/{id}/requirements/approved` | → `{ sessionId, version }`, the latest approved version; `404` if none. |

Session states: `queued → discovering ⇄ ready-for-review → awaiting-approval → approved`, with
`awaiting-approval → needs-changes → discovering`, plus `cancelled` (and `failed`, reserved for terminal
problems). A failed turn leaves the session in `discovering`. Approved versions are immutable.

## 6. Files

| Method | Path                                   | Notes                                |
| ------ | -------------------------------------- | ------------------------------------ |
| GET    | `/projects/{id}/files`                 | → `FileNode` tree                    |
| GET    | `/projects/{id}/files/{path}`          | → raw contents (`text/plain`)        |
| PUT    | `/projects/{id}/files/{path}`          | raw contents → `204`                 |
| DELETE | `/projects/{id}/files/{path}`          | → `204`                              |

Paths are normalised and confined to the project root (reject `..`, absolute paths, and symlinks).

## 7. Sandboxed execution (internal only)

Not exposed to the browser. Workers implement `SandboxExecutionService` and `BrowserAutomationService`.

Mandatory isolation requirements:

- One ephemeral sandbox per run (for example Firecracker or gVisor microVMs, or rootless containers with seccomp).
  Never on the API host.
- `SandboxLimits` enforced: CPU, memory, wall-clock timeout, process count, disk quota.
- Network is default-deny, with an allow-list limited to package registries through a caching proxy.
- No access to production credentials, the metadata service, or other tenants' data. Run as a non-root user with a
  read-only base image and a writable scratch volume only.
- All commands, exit codes, and output are logged and streamed as `BuildLogEntry`.

## 8. Builds, tests, repair

| Method | Path                               | Notes                                  |
| ------ | ---------------------------------- | -------------------------------------- |
| POST   | `/projects/{id}/builds`            | → `202 BuildRun`                       |
| GET    | `/builds/{buildId}`                | → `BuildRun`                           |
| GET    | `/builds/{buildId}/logs`           | SSE stream of `BuildLogEntry`          |
| POST   | `/projects/{id}/test-runs`         | → `202 TestRun`                        |
| GET    | `/test-runs/{testRunId}`           | → `TestRun` with every `TestResult`, failures included |
| POST   | `/test-runs/{testRunId}/repairs`   | → `202 RepairAttempt`                  |

## 9. Export and deployment

| Method | Path                              | Notes                                              |
| ------ | --------------------------------- | -------------------------------------------------- |
| POST   | `/projects/{id}/exports`          | → `202`, then `PackageArtifact` (signed, expiring URL, SHA-256) |
| POST   | `/projects/{id}/deployments`      | `{ target }` → `202 Deployment`                    |
| GET    | `/deployments/{deploymentId}`     | → `Deployment`                                     |

Until these exist, the workspace's **Export** dialog states that ZIP export is unavailable and offers the real
`omniora.project.json` download instead.
