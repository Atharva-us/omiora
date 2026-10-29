# Omniora frontend architecture

Status: the frontend runs in **demo mode** (browser storage, no backend) or **API mode** (the FastAPI backend in
`backend/`, documented in [BACKEND.md](BACKEND.md)). API mode provides accounts, project persistence, and Agent 1
(Project Manager) planning and Agent 2 (Requirements Analyst) discovery, each with human approval. Agents 3–10, code
generation, and execution do not exist yet. This
document describes the frontend structure in `src/` and the boundaries the backend plugs into. Findings that motivated the structure are in
[ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md); contributor rules are in
[ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md); the HTTP API draft is in
[BACKEND_CONTRACTS.md](BACKEND_CONTRACTS.md).

## 1. Layers

```
src/
  main.tsx            Bootstrap: parse config → compose services → render (or show startup error)
  app/
    configuration/    parseAppConfig(): the only reader of import.meta.env
    composition/      createServices(): the only place that picks concrete adapters
    providers/        ServicesProvider (React context)
    router/           Route table, browser router factory
    error-handling/   RouteErrorPage (route boundary), StartupErrorScreen
  domain/             Pure business model. No React, browser, HTTP, or app imports
    errors.ts         AppError + finite AppErrorCode set + toUserMessage()
    projects/         Zod schemas and types, catalog, rules, stack validation, lifecycle, definition export
    authentication/   Auth value types and credential rules
    engineering/      AGENT_ROLES (the ten planned agents) and future engine types
    runs/             Run, plan, task, approval, and event schemas (mirror of the backend)
  services/
    contracts/        ProjectService, AuthenticationService, RunService, engine contracts (interfaces only)
    demo/             Demo ProjectService over a KeyValueStore + sample fixtures
    http/             API-mode adapters: shared client, projects, auth, runs (SSE)
    unconfigured/     Demo-mode auth and runs that honestly report "not available"
    capabilities.ts   What this build can actually do (rendered on /status)
    services-context.ts  The Services interface and React context
  infrastructure/     Adapters behind ports: KeyValueStore (browser/memory), Logger (console/memory)
  components/         Shared UI: ui/ primitives, layout/, navigation/, brand/, project/ (shared project presentation)
  features/           One folder per product area; components, local models, and tests together
  hooks/              useServices, useAsyncData, useErrorReporter, useScrollToHash
  lib/                Small framework-agnostic helpers (class names, formatting, file download)
  test/               Test helpers, fixtures, and reusable contract suites
```

### Dependency direction

```
            features ─────────────┐
               │                  │ (type-only)
   components ─┤                  ▼
               ├──► hooks ──► services/contracts ──► domain ◄── infrastructure
               │                  ▲                     ▲
               └──────────────────┼─────────────────────┘
                                  │
   app/composition ──► services/demo, services/unconfigured, infrastructure (the only concrete wiring)
```

The rules are enforced by ESLint (`@typescript-eslint/no-restricted-imports` in `eslint.config.js`) and break
the build if violated:

| Code in | May not import |
| --- | --- |
| `domain/` | React, React Router, Lucide, or any other `src/` layer. Only other domain modules and `zod/mini` |
| `services/`, `infrastructure/`, `lib/` | `app/`, `components/`, `features/`, `hooks/` |
| `components/`, `hooks/` | concrete adapters (`services/demo`, `services/unconfigured`, `app/composition`), `features/`; `infrastructure/` only as types |
| `features/` | other features, concrete adapters; `infrastructure/` only as types |

A feature that needs another feature's code is a signal to move that code to `domain/` (rules),
`components/` (shared UI), or `lib/` (helpers).

## 2. Composition and configuration

`main.tsx` calls `parseAppConfig(import.meta.env)` and then `createServices(config)`. Either may throw
`AppError('configuration')`, which renders `StartupErrorScreen` instead of the app.

| Variable | Values | Default | Notes |
| --- | --- | --- | --- |
| `VITE_OMNIORA_SERVICE_MODE` | `demo`, `api` | `demo` in development only; **required for production builds** | `api` uses the HTTP adapters and fails visibly if the backend is unreachable. There is never a fallback between modes. |
| `VITE_OMNIORA_API_BASE_URL` | absolute URL | none | Required in `api` mode. Must use https (http only for localhost in development); no embedded credentials. |
| `VITE_OMNIORA_LOG_LEVEL` | `debug` … `silent` | `debug` in development, `warn` in production | |

**Public versus private configuration.** Every `VITE_*` value is inlined into the public bundle. The frontend
holds no secrets. Model provider keys, database URLs, signing keys, and sandbox credentials live only in backend
configuration. `parseAppConfig` refuses to start if a `VITE_*` variable name looks like a secret (`*_API_KEY`,
`*TOKEN*`, `*SECRET*`, and so on), and never echoes values in its messages.

`Services` (in `services/services-context.ts`) is what UI code receives from `useServices()`:
`{ mode, projects, auth, uiState, logger }`, all typed by interface. Swapping demo adapters for HTTP adapters
changes only `app/composition/create-services.ts`.

## 3. Domain model

- **Schemas are the source of truth.** `domain/projects/project.ts` defines Zod schemas, and the TypeScript types
  are inferred from them, so the validator and the type cannot drift. Shape validation runs wherever data enters
  from outside the type system: persisted storage, router state, and later API responses.
- **Business rules are separate from shape.** `domain/projects/rules.ts` holds the limits (`PROJECT_LIMITS`), field
  validators, `validateProjectConfiguration`, and `normalizeConfiguration`. Both the UI (for immediate feedback)
  and every `ProjectService` (as enforcement) call them.
- **One source of truth per fact.** `Project` is `{ id, source, status, configuration, createdAt, updatedAt }`.
  The name, description, platform, and stack live only in `configuration`; technologies are derived with
  `projectTechnologies()`.
- **Discriminated unions where data differs.** `StackPreference` is `{ mode: 'recommend' }` or
  `{ mode: 'custom', technologies }`. The wizard's UI-only `WizardDraft` may remember technologies while
  "recommend" is selected; `toConfiguration()` converts it to the domain type before saving.
- **Lifecycle.** `ProjectStatus` is a finite set, and `canTransition()` encodes the allowed edges
  (`draft → configured → queued → planning → generating → testing → ready`, with `repairing` and `failed` branches;
  there is no path to `ready` that skips `testing`). The frontend only ever creates `configured` projects. Engine
  states will be set by the backend.
- **Identifiers are opaque strings assigned by the service implementation.** UI code never creates ids. The demo
  adapter generates `prj_…` and `note_…` locally (`services/demo/ids.ts`); the API adapter will use server ids.

## 4. Errors, loading, and diagnostics

- Services throw only `AppError` with a code from `APP_ERROR_CODES`. An `AppError` message must be safe to show.
  Technical detail goes in `cause` (logged, never rendered); user-safe specifics go in `details`.
- UI code converts errors with `useErrorReporter()` or `toUserMessage()`. Unknown errors become a generic message
  and are logged, because they indicate bugs. Raw `error.message` is never rendered.
- `useAsyncData(loader, event)` returns `{ data, errorMessage, isLoading, reload }`. Pages render loading, error
  (with **Retry**), empty, and data states explicitly.
- Every layout route has `errorElement: <RouteErrorPage />`. It shows a safe message and recovery links, logs
  `route.render-failed`, and shows stack traces only in development builds.
- `Logger` (`infrastructure/telemetry/logger.ts`) takes dot-separated events and flat context. It redacts values
  under keys matching password, secret, token, authorization, cookie, api-key, credential, or session, and
  flattens `Error` objects (stacks only in development). A remote sink can implement the same interface later.

## 5. Persistence

| Data | Where | Failure behaviour |
| --- | --- | --- |
| Projects, history, notes (API mode) | PostgreSQL via the API | API errors are mapped to `AppError` and shown with retry or sign-in actions. |
| Projects, history, notes (demo mode) | `KeyValueStore` → localStorage (`omniora.demo.v1`) | Write failures throw `storage-unavailable` and the UI shows them. Invalid records are dropped one by one and logged (`demo-store.invalid-records-dropped`). |
| Wizard draft | `services.uiState` → sessionStorage (`omniora.wizard.draft`) | Best effort: failures are logged and the wizard keeps working. Malformed drafts are discarded. |
| Credentials, tokens | Never in web storage | Future auth must use HttpOnly, Secure, SameSite cookies. |

Phase 1 records (with duplicated top-level fields and `technologies: []` on "recommend" stacks) still parse,
because Zod strips unknown keys. A test covers this.

## 6. Testing layers

| Layer | Where | Examples |
| --- | --- | --- |
| Unit | `*.test.ts` beside pure modules | rules, stack validation, schemas, lifecycle, config parsing, logger redaction, filters, wizard model |
| Contract | `src/test/contracts/*.contract.ts`, run from adapter tests | `describeProjectServiceContract()`: every `ProjectService` (demo now, HTTP later) must pass it |
| Integration | adapter and composition tests | storage failures, corrupted data, legacy data, api-mode refusal |
| Component and flow | `*.test.tsx` | wizard end to end, dashboard filters, workspace, auth screens, route error boundary |
| Regression | colocated, labelled `Regression for audit R#` | R1–R4 from the audit, same-millisecond ordering |

UI tests render the real route tree through the real composition root (`renderApp()` / `createTestServices()`)
with jsdom storage and a memory logger, so they exercise the same wiring as production.

## 7. Security posture

- No `dangerouslySetInnerHTML`, `eval`, `new Function`, or `innerHTML`. All user text renders as React text.
- User-supplied URLs are stored and displayed as text, never rendered as links. Validation allows only
  `http:`/`https:` (`isHttpUrl`), so `javascript:` and `data:` are rejected at both the UI and service boundaries.
- Router state, persisted data, and URL query parameters are parsed with schemas or narrowing helpers before use.
- Downloads are built from a sanitised filename (`slugify`) and JSON text only.
- The frontend never receives secrets (see §2).
- **Hosting requirements (not enforceable from this repository):** serve over HTTPS with HSTS, and set a
  Content-Security-Policy. A starting point compatible with this build:
  `default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data: blob:; connect-src 'self' <API origin>; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`.
  Verify it against the deployed build before enforcing it.
- No third-party requests: the Geist typefaces are bundled (SIL OFL 1.1; licence texts are served from `/licenses/`).

## 8. Agent system foundations (not implemented)

The ten planned agents (`AGENT_ROLES` in `domain/engineering/types.ts`) are **backend** components. The frontend
will only start runs, render progress, answer approval requests, and display artifacts. No orchestration logic
belongs in React components.

### Boundaries the backend must define before Agent 1

| Concern | Decision to make | Where it lives |
| --- | --- | --- |
| Agent definition | Role, versioned instructions, allowed tools, model route, input and output schemas | Backend registry; the frontend sees only `AgentRole` and display copy |
| Input/output contracts | Typed, schema-validated payloads per agent (for example Requirements Analyst → `AnalysedRequirement[]`) | Backend schemas mirrored as Zod or OpenAPI types in `services/contracts` |
| Task assignment | Project Manager agent produces `EngineeringTask[]` with dependencies; the orchestrator dispatches | Backend orchestrator |
| Workflow orchestration | Explicit state machine per run (a DAG of tasks), not free-form agent chat | Backend orchestrator |
| Durable job state | Runs, tasks, and attempts persisted in PostgreSQL; workers resume from state, not memory | Backend database plus queue |
| Tool permissions | Allow-list per agent (read repository, write files, run sandbox command, browse reference URL) | Backend policy, checked on every tool call |
| Execution environments | Ephemeral sandbox per run with CPU, memory, time, and egress limits (`SandboxLimits`) | Isolated workers, **never** the API host |
| Events and progress | Append-only run event log; SSE stream to the UI (`AgentActivity`, `BuildLogEntry`) | Backend; UI consumes through a service contract |
| Retry policy | Per task: max attempts, backoff, and which error classes are retryable | Orchestrator configuration |
| Cancellation | Cooperative cancel token checked between tool calls, plus a hard sandbox kill | Orchestrator and sandbox |
| Artifacts | Content-addressed storage (SHA-256) for files, test reports, and ZIPs; referenced by id | Object storage |
| Audit trail | Who or what did what, when, with which inputs (prompt hashes, tool calls, diffs) | Append-only table |
| Human approval gates | Run pauses at defined checkpoints (plan approval, architecture approval, before release) until a user approves or rejects | Orchestrator state `awaiting-approval`; UI renders the pending decision |

### Foundation for Agent 1 (delivered in Phase 2)

1. FastAPI service implementing the Projects API (BACKEND_CONTRACTS §2) and authentication (§3).
2. An HTTP `ProjectService` adapter that passes `describeProjectServiceContract`, wired in `app/composition`.
3. Persistent `runs`, `run_events`, and `tasks` tables, with a worker queue that can resume runs.
4. A run event stream (SSE) and a frontend `RunService` contract with one adapter.
5. Model routing behind a backend interface, with keys held only server-side.
6. An approval-gate mechanism, because Agent 1's plan must be approved before any later agent runs.

All six exist (see [BACKEND.md](BACKEND.md)). Still missing before Agents 3–10: tool permissions and an audited
tool-call layer, sandboxed execution, artifact storage, task-level orchestration that consumes approved plans,
and per-agent evaluation suites.

### Agent 2: Requirements Analyst (delivered in Phase 3)

The frontend side is thin. `RequirementsService` (`services/contracts/requirements-service.ts`) has an HTTP
adapter and an unavailable adapter for demo mode, which simulates nothing. Zod schemas in
`domain/requirements/requirements.ts` parse every response. The workspace **Requirements** tab
(`features/workspace/requirements/`) renders questions, answers, versions, and approval. It subscribes to the
session's events through `RunService.subscribe`, because a session id is a run id, and re-fetches the session
after each event. The analysing indicator appears only while the server reports a queued or running turn. Answer
drafts restart from the server's recorded answers whenever those change, so a refresh resumes exactly. Retried
submissions reuse their idempotency key. The Plan tab starts planning from the approved version, or through a
separate, labelled "Plan without requirements" path.

Agent 1 needs no sandbox (it plans and writes no code). Sandboxed execution must exist before the Frontend,
Backend, Mobile, Database, or QA agents run anything.
