# Architecture audit: Phase 1 frontend

Audit date: 2026-10-29. Scope: everything under `src/`, the build, lint, test, and TypeScript configuration,
`README.md`, and `docs/BACKEND_CONTRACTS.md`.

## Method and baseline

Evidence was gathered by running tools, not by reading alone:

| Check | Tool | Baseline result |
| --- | --- | --- |
| Type-check | `npm run typecheck` (`tsc -b`, strict) | pass |
| Lint | `npm run lint` (ESLint, typescript-eslint, react-hooks) | 0 errors, 0 warnings |
| Tests | `npm test` (Vitest + Testing Library) | 45/45 passing in 8 files |
| Coverage | `vitest --coverage` (v8, `src/**`) | 82.16% statements, 78.43% branches, 85.31% functions, 83.81% lines |
| Build | `npm run build` | pass; one JS chunk of 444.6 kB (134.7 kB gzip) |
| Dependencies | `npm audit` | 0 known vulnerabilities |
| Import graph | custom script over all 101 `src` files | **0 circular imports**; 3 cross-feature imports |
| Unused exports | custom script | 1 unused function, 1 unused barrel file, 2 unused style options |
| Reproductions | temporary Vitest file (deleted afterwards) | 4 defects reproduced (R1–R4 below) |

Reproduced defects:

- **R1.** A persisted project whose `technologies` contains an unknown id (`"cobol"`) makes `/projects` render
  React Router's default **"Unexpected Application Error! Unknown technology: cobol"** screen.
- **R2.** With `Storage.setItem` throwing `QuotaExceededError`, `createProject()` resolves successfully and returns
  a project id, but `getProject(id)` then returns `null`. The project is silently lost and the user lands on
  "Project not found".
- **R3.** `createProject()` accepts a React + Next.js stack that the wizard forbids. `updateProject()` accepts a
  500-character name (the UI limit is 80), and `addNote()` accepts a 5,000-character note (the UI limit is 1,000).
- **R4.** A malformed wizard draft in `sessionStorage` (an unknown technology id) crashes `/new` with the same
  default error screen.

Strengths worth keeping: no circular imports, no `any`, no `dangerouslySetInnerHTML`, `eval`, or `new Function`,
strict TypeScript including `noUncheckedIndexedAccess`, services reached only through `useServices()`, and honest
labelling of unconnected features.

## Findings

Severity: **High** means a user-visible failure or data loss that can be reproduced. **Medium** means a structural
problem that will cause defects as the backend and agents arrive. **Low** means local quality issues.
**Info** means an observation or deferred item.

| ID | Severity | Finding | Evidence | Resolution |
| --- | --- | --- | --- | --- |
| A-01 | High | Persisted data is validated only at the top level, so any malformed entry crashes rendering. | `services/demo/local-project-service.ts` `isDemoStore` checks only that the arrays exist; `lib/catalog.ts` `getTechnology` throws on unknown ids. Reproduced as R1. | Fixed. Zod schemas validate each persisted record. Invalid records are dropped and logged. |
| A-02 | High | No route-level error boundary. Any render error shows React Router's default screen with the raw exception text. | `app/routes.tsx` defines no `errorElement`. R1 and R4 show "Unexpected Application Error!". | Fixed. `RouteErrorPage` on every layout route: safe message, recovery links, diagnostics in development only. |
| A-03 | High | Storage write failures are swallowed, so persistence reports success after losing data. | `lib/storage.ts` `writeJson` catches and ignores every error, and the demo adapter relies on it. Reproduced as R2. | Fixed. `KeyValueStore.set` throws `AppError('storage-unavailable')`; the adapter propagates it and the UI shows it. |
| A-04 | Medium | The service boundary does not enforce domain rules, so the UI is the only validator. A future API client or agent could persist invalid data. | `createProject` checks only for an empty name and description; `updateProject` validates nothing about the configuration; `addNote` has no length limit. Reproduced as R3. | Fixed. The adapter enforces the shared domain rules and throws `AppError('validation')` with details. |
| A-05 | Medium | Domain rules are owned by a UI feature and duplicated. | Limits live in `features/project-creation/wizard-model.ts` and are imported by `features/landing/ProjectPrompt.tsx` and `features/workspace/modals/SettingsModal.tsx`. `SettingsModal.tsx` reimplements name validation. `ChatPanel.tsx` owns `NOTE_MAX_LENGTH`, which the service does not know. | Fixed. Moved to `domain/projects/rules.ts`, used by the UI and the service alike. |
| A-06 | Medium | `Project` stores the same facts twice: `name`, `description`, `platform`, and `technologies` both at the top level and inside `configuration`. | `types/project.ts`; manual synchronisation in `local-project-service.ts` `updateProject`. | Fixed. `Project` has one source of truth (`configuration`); technologies are derived. Existing stored data still parses because Zod strips the old keys. |
| A-07 | Medium | `StackPreference` is not a discriminated union. "Recommend" mode persists a technology list that UI code must remember to clear. | `types/technology.ts`; `finaliseConfiguration` in `wizard-model.ts` exists to clear it; samples persist `technologies: []`. UI-only state leaks into persisted data. | Fixed. `{ mode: 'recommend' } \| { mode: 'custom', technologies }`. The wizard keeps its remembered selection in a separate draft type. |
| A-08 | Medium | Service composition is hard-wired and there is no configuration, so demo mode is implicit and no non-demo mode can be selected or rejected. | `services/services-context.ts` `createDefaultServices()` always builds the demo adapters; `import.meta.env` is not read anywhere. | Fixed. `app/configuration` parses and validates the environment; `app/composition` wires adapters per mode. `api` mode fails at startup with a clear error and never falls back to demo. |
| A-09 | Medium | Error handling is inconsistent: two unrelated error classes, and raw messages from unknown errors are shown to users. | `ProjectServiceError` and `AuthError` share no base. `error instanceof Error ? error.message : …` appears in `ProjectWizard.tsx`, `ChatPanel.tsx`, and twice in `SettingsModal.tsx`, so a `TypeError` message would be shown verbatim. | Fixed. One `AppError` with a finite code set; `toUserMessage()` shows only messages known to be safe; unexpected errors are logged. |
| A-10 | Medium | Features call browser storage directly, with the storage key spread across three files. The demo adapter is bound to `window` storage and cannot be tested without patching globals. | `NewProjectPage.tsx`, `ProjectWizard.tsx`, and `wizard-model.ts` (`WIZARD_DRAFT_KEY`); `local-project-service.ts` imports `lib/storage`. | Fixed. `KeyValueStore` interface in `infrastructure/storage` is injected through composition; wizard drafts go through `wizard-draft.ts`. |
| A-11 | Low | Unchecked type assertions on DOM values, and URL-parsing logic inside a page component. | `ProjectFiltersBar.tsx` casts `value as ProjectFilters[...]` three times; `ProjectsPage.tsx` holds `readFilters`, `writeFilters`, and `pick`. | Fixed. Parsing moved into `filter-projects.ts` with narrowing helpers and unit tests. |
| A-12 | Low | Cross-feature imports. | `workspace/ProjectSummary.tsx` imports `features/projects/ProjectStatusBadge`; `landing` and `workspace` import `project-creation/wizard-model`. | Fixed. Shared presentation moved to `components/project`, rules to `domain`. ESLint now rejects cross-feature imports. |
| A-13 | Low | No logging or diagnostics interface. Failures are swallowed (storage) or never reported (render errors). | No logger anywhere in `src/`. | Fixed. Small `Logger` interface with a console implementation that redacts sensitive keys and is level-gated by configuration. |
| A-14 | Low | The agent roster contradicts the roadmap: six generic roles rather than the ten planned agents. | `types/engineering.ts` `AgentRole`; the "Planned agents" list in `features/workspace/AgentActivityPanel.tsx`. | Fixed. A single `AGENT_ROLES` list for the ten planned agents, used by the panel. Still labelled as not connected. |
| A-15 | Low | Dead code. | `lib/format.ts` `formatTime` is unused; `types/index.ts` barrel is never imported; the `outline` variant and `icon` size in `button-styles.ts` are unused. | Fixed. Removed. |
| A-16 | Low | Test-runner globals are typed into application code. | `tsconfig.app.json` `types: ["vitest/globals"]` and `globals: true`, although every test imports from `vitest` explicitly. | Fixed. Globals disabled; tests keep explicit imports. |
| A-17 | Low | Tabs reference panels that do not exist. | `components/ui/Tabs.tsx` sets `aria-controls` on every tab, but only the selected panel is rendered. | Fixed. `aria-controls` only on the selected tab. |
| A-18 | Low | The download helper revokes its object URL synchronously after `click()`, which some browsers handle by aborting the download. DOM side effects were also mixed with pure serialisation in `lib`. | `lib/project-definition.ts` `downloadProjectDefinition`. | Fixed. Pure serialisation is in `domain/projects/project-definition.ts`; `lib/download.ts` revokes the URL on the next task. |
| A-19 | Info | One eagerly loaded bundle for every route. | `app/routes.tsx` imports all pages statically; one 444.6 kB chunk. | Deferred. 134.7 kB gzip is acceptable for now. Revisit with route `lazy()` once the workspace grows (an editor or terminal will). |
| A-20 | Info | Third-party and hosting-level security gaps. | `index.html` loads Google Fonts, which discloses visitor IPs to Google and is not mentioned on the Privacy page. There is no Content-Security-Policy, which must be set by the host. | Fixed in Phase 2: fonts self-hosted (SIL OFL 1.1) and the Google request removed. A CSP is still the host's job; the recommended policy is in `docs/ARCHITECTURE.md`. |
| A-21 | Info | No contract tests. The only `ProjectService` implementation is tested directly, so a future HTTP adapter has no executable specification to satisfy. | `services/demo/local-project-service.test.ts`. | Fixed. Reusable contract suite at `src/test/contracts/project-service.contract.ts`, run against the demo adapter. |
| A-22 | Medium | *Found while writing the contract tests.* History and project lists sorted only by timestamp, so events in the same millisecond came back oldest first, which breaks the "newest first" contract. One `updateProject` call that renames and reconfigures always records two events with identical timestamps. | The adapter tests failed intermittently when run in isolation (3 of 3 runs at one point). The cause was `.sort((a, b) => b.at.localeCompare(a.at))` in the demo adapter. | Fixed. Ties fall back to reverse insertion order (the stores are append-only). A deterministic regression test uses a frozen clock. |

## Results after the refactor

| Check | Before | After |
| --- | --- | --- |
| Type-check | pass | pass |
| Lint | pass (no boundary rules) | pass, with import boundaries enforced; each rule verified by planting a violation |
| Tests | 45 in 8 files | 99 in 17 files; all 45 original scenarios kept (updated to the new API; every changed assertion was checked to be equal or stronger) |
| Coverage, same command as baseline (`--coverage.include='src/**'`) | 82.16% statements, 78.43% branches, 85.31% functions, 83.81% lines | 86.89% statements, 83.93% branches, 86.71% functions, 87.80% lines |
| Circular imports | 0 | 0 |
| Cross-feature imports | 3 | 0 |
| Bundle (JS) | 444.6 kB / 134.7 kB gzip | 482.2 kB / 146.7 kB gzip (+12 kB gzip: `zod/mini`, logger, configuration, error boundary). Full `zod` cost +29 kB gzip and was rejected. |
| `npm audit` | 0 vulnerabilities | 0 vulnerabilities |
| Production smoke test (headless Chrome) | n/a | every route renders, create flow reaches the workspace, a corrupted store does not break the dashboard, 0 console errors |

## Not changed, deliberately

- **Visual design, copy, routes, and page behaviour.** Preserved; the refactor is structural.
- **Colocated tests.** Feature tests stay next to the code they cover instead of moving to a top-level `tests/` tree.
  Shared helpers and contract suites live in `src/test/`.
- **State management.** No global store is added. Server state is loaded per route through `useAsyncData`, and
  UI state is component-local. This is adequate until live event streams arrive.
- **No dependency-injection framework.** A composition function and React context are sufficient.

## Decisions (approved for Phase 2)

1. Fonts: self-host the licensed Geist files and remove the Google Fonts dependency. **Done.**
2. Configuration: demo mode is allowed by default only in development; production builds must set
   `VITE_OMNIORA_SERVICE_MODE`, and there is never a silent fallback to demo. **Done.**
3. Identifiers: server-generated UUIDv7 for persisted entities; client ids only for local demo data. **Done.**
4. Git: initialise the repository, review `.gitignore`, and inspect staged files; the first commit needs explicit
   approval. **Repository initialised; awaiting approval to commit.**
