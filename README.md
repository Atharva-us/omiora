# Omniora

**The Intelligence to Build Anything.**

An AI-powered software engineering platform that transforms ideas into complete, testable, downloadable software.

This repository holds the React frontend and, in `backend/`, the FastAPI service. The frontend runs in two modes:

- **Demo mode:** no backend; projects are stored in your browser and no agent runs.
- **API mode:** accounts, PostgreSQL persistence, and **Agent 1 (Project Manager)**, which drafts a plan that you
  approve, revise, or reject.

No code is generated or executed yet. Agents 2–10 are planned, not built. The in-app `/status` page and
[What is real today](#what-is-real-today) list exactly what works.

## Getting started

Requirements: Node.js 20.19+ or 22.12+ (developed on Node 22.17, npm 10.9).

```bash
npm install        # install dependencies
npm run dev        # dev server at http://localhost:5173 (demo mode by default in development)
npm run check      # type-check + lint + all tests + production build (run before every change)
```

For API mode, set up and start the backend and a worker ([docs/BACKEND.md](docs/BACKEND.md)), then:

```bash
VITE_OMNIORA_SERVICE_MODE=api VITE_OMNIORA_API_BASE_URL=http://localhost:8000 npm run dev
```

Production builds must set the mode explicitly:

```bash
VITE_OMNIORA_SERVICE_MODE=demo npm run build
VITE_OMNIORA_SERVICE_MODE=api VITE_OMNIORA_API_BASE_URL=https://api.example.com npm run build
```

| Script | Purpose |
| --- | --- |
| `npm run dev` | Vite dev server |
| `npm run build` | Type-check and build into `dist/` |
| `npm run preview` | Serve the production build |
| `npm run typecheck` | TypeScript (strict) |
| `npm run lint` | ESLint, including architectural import boundaries |
| `npm test` | All tests (Vitest + Testing Library) |
| `npm run test:unit` | Unit, contract, and integration tests (`*.test.ts`) |
| `npm run test:ui` | Component and flow tests (`*.test.tsx`) |
| `npm run test:coverage` | Tests with v8 coverage (summary in the terminal, HTML in `coverage/`) |
| `npm run check` | Everything above that gates a change |

Optional: run the ProjectService contract suite against a live API with
`VITE_OMNIORA_CONTRACT_API_URL=http://localhost:8000 npx vitest run src/services/http/project-service.api.test.ts`
(it registers throwaway accounts, so use a development database).

## Configuration

Optional. Copy `.env.example` to `.env.local` to override defaults. All variables are **public** (embedded in
the bundle), so never put secrets in them; the app refuses to start if a variable name looks like one.

| Variable | Default | Meaning |
| --- | --- | --- |
| `VITE_OMNIORA_SERVICE_MODE` | `demo` in development; **required in production** | `demo` (browser storage) or `api` (backend) |
| `VITE_OMNIORA_API_BASE_URL` | none | Backend origin, required in `api` mode (https) |
| `VITE_OMNIORA_LOG_LEVEL` | `debug` in dev, `warn` in prod | `debug`, `info`, `warn`, `error`, or `silent` |

## Architecture in one minute

```
backend/           FastAPI service: auth, projects, durable runs, worker, Project Manager agent (docs/BACKEND.md)
src/
  app/             bootstrap: configuration, composition root, providers, router, error boundaries
  domain/          pure business model: Zod schemas, rules, lifecycle, errors (no React or browser)
  services/        contracts/ (interfaces), http/ (API mode), demo/ and unconfigured/ (demo mode), capabilities
  infrastructure/  storage and logging adapters
  components/      shared UI
  features/        landing, project-creation, projects, workspace, authentication, info
  hooks/ lib/ styles/ test/
```

- UI code reaches data only through `useServices()`, which is typed by interfaces.
- Concrete adapters are chosen in exactly one place: `src/app/composition/create-services.ts`.
- Domain rules are shared by the UI and the services, so they cannot disagree.
- Everything read from storage, router state, or URLs is validated before use.
- Import boundaries are enforced by ESLint.

Read next:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): layers, dependency rules, errors, persistence, security, and
  agent-system foundations.
- [docs/ENGINEERING_STANDARDS.md](docs/ENGINEERING_STANDARDS.md): rules for contributors and AI agents.
- [docs/BACKEND.md](docs/BACKEND.md): backend setup, worker, runs, security, limitations.
- [docs/BACKEND_CONTRACTS.md](docs/BACKEND_CONTRACTS.md): the HTTP API (implemented sections marked).
- [docs/PHASE_2_IMPLEMENTATION_PLAN.md](docs/PHASE_2_IMPLEMENTATION_PLAN.md): Phase 2 design and status.
- [docs/ARCHITECTURE_AUDIT.md](docs/ARCHITECTURE_AUDIT.md): audit findings and their resolutions.

## Routes

| Path | Page |
| --- | --- |
| `/` | Landing page with the project prompt |
| `/new` | Four-step project creation wizard |
| `/projects` | Projects dashboard (search, filters, sample section) |
| `/projects/:id` | Project workspace |
| `/projects/:id/edit` | Edit a project's configuration |
| `/sign-in`, `/register`, `/forgot-password` | Authentication screens (provider not connected) |
| `/status` | What is and is not connected in this build |
| `/privacy`, `/terms` | Placeholder pages stating the policies are unpublished |

## What is real today

| Area | Demo mode | API mode |
| --- | --- | --- |
| Project wizard, dashboard, workspace | Real; stored in this browser | Real; stored in PostgreSQL per account |
| Accounts | Not available (sign-in honestly fails) | Email and password, HttpOnly session cookie; no email verification or password reset yet |
| Project Manager agent | Not available (explained in the Plan tab) | Real: validated plan, open questions, proposed tasks, approve / revise / reject, live persisted events. Requires a model provider on the server (`OMNIORA_MODEL_PROVIDER` with `ANTHROPIC_API_KEY` or `GROQ_API_KEY`); validated live on Groq `openai/gpt-oss-120b`. |
| Sample projects | Fixed, labelled "Demo data", read-only | Same |
| Agents 2–10, code generation, sandbox, build, tests, repair, ZIP export, deploy | Not built | Not built (approving a plan executes nothing) |

## Security notes

- Passwords never reach web storage (tested). In API mode the session lives in an HttpOnly cookie that
  JavaScript cannot read (verified in a real browser). The frontend holds no secrets, and startup is refused if a `VITE_*`
  variable name looks like a secret (tested).
- No `dangerouslySetInnerHTML`, `eval`, or dynamic code execution. User text renders as text; user URLs are never
  rendered as links and must be `http(s)`.
- Persisted data, router state, and query parameters are schema-validated, and corrupted records are dropped.
- Generated code must never run on the application server. Execution belongs in isolated sandboxes (see
  `docs/ARCHITECTURE.md` §7–8).
- Hosting must add HTTPS, HSTS, and a Content-Security-Policy (a suggested policy is in `docs/ARCHITECTURE.md` §7).
