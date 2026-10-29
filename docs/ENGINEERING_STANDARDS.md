# Engineering standards

Rules for every contributor, human or AI agent. They describe how this repository works today; where a rule is
enforced by tooling, the tool is named. Read [ARCHITECTURE.md](ARCHITECTURE.md) first.

## Before you open a change

Run `npm run check` (type-check, lint, all tests, production build). It must pass locally. Never weaken a
TypeScript option, disable a lint rule, skip a test, or loosen an assertion to make it pass.

## Naming and files

- Components use `PascalCase.tsx` with one primary exported component. Modules use `kebab-case.ts`.
- Hooks are `use-thing.ts` and export `useThing`. Tests sit beside the code: `thing.test.ts(x)`.
- Component files export only components (types are fine). Constants and helpers go in a sibling `.ts` file
  (enforced by `react-refresh/only-export-components`).
- Prefer descriptive names (`validateProjectName`, `projectTechnologies`) to abbreviations.
- Log events are dot-separated and past tense or failure-shaped: `wizard-draft.save-failed`, `route.render-failed`.

## Where code goes

| You are writing | Put it in |
| --- | --- |
| A business rule, limit, schema, or domain type | `src/domain/` (pure TypeScript and `zod/mini` only) |
| A service interface | `src/services/contracts/` |
| A concrete adapter (storage, HTTP, logging) | `src/infrastructure/` or `src/services/<family>/`, wired only in `src/app/composition/` |
| UI used by one feature | that feature's folder |
| UI used by several features | `src/components/` |
| A small framework-agnostic helper | `src/lib/` |

Cross-feature imports, domain imports of React or the browser, and UI imports of concrete adapters fail lint.

## TypeScript

- `strict`, `noUncheckedIndexedAccess`, `noUnusedLocals`, `noUnusedParameters`, `erasableSyntaxOnly`, and
  `verbatimModuleSyntax` stay on.
- No `any`. Avoid `as` assertions. Narrow untrusted values with a schema or a lookup (see `pick()` in
  `features/projects/filter-projects.ts`). The only acceptable assertions are documented, local, and follow a check.
- Model finite sets as `as const` arrays plus derived unions, and key lookup tables by the union
  (`Record<TechnologyId, …>`), so adding a member forces every table to be updated.
- Use discriminated unions when variants carry different data.

## Data crossing a boundary

- Anything from storage, the network, URL parameters, router state, or files is `unknown` until parsed.
- Validate shape with the domain schema (`safeParse`) and business rules with `domain/projects/rules.ts`.
- Services enforce rules even if the UI already checked. A future backend must enforce them too.

## Errors

- Throw `AppError(code, safeMessage, { cause, details })` from services. Add a code to `APP_ERROR_CODES` only
  when callers need to branch on it.
- Never render `error.message` from an unknown error. Use `useErrorReporter()` or `useAsyncData()`, which log
  unknown errors and show safe text.
- Never swallow an error silently. Best-effort operations (for example draft persistence) must log a warning.
- Every async view has loading, error with retry, empty, and success states.

## Logging

- Log through `services.logger`, not `console`. The only exception is `main.tsx`, before services exist.
- Never log passwords, tokens, keys, cookies, full request bodies, or personal data. Redaction is a safety net,
  not permission.

## Configuration and secrets

- Read environment variables only in `app/configuration/app-config.ts`, and validate them there.
- `VITE_*` variables are public. Secrets never go in the frontend, `.env.example`, tests, or fixtures.
- A misconfigured production must fail visibly. Never fall back to demo adapters silently.
- Commit `.env.example` only when it matches what `parseAppConfig` actually reads.

## Testing

Every change adds or updates tests at the lowest layer that proves it:

- **Pure logic** gets a unit test (`*.test.ts`).
- **A new or changed service** must pass the contract suite. Add cases to the suite when the contract changes.
- **User-facing behaviour** gets a component or flow test (`*.test.tsx`) through `renderApp()`, querying by role
  and accessible name, not CSS classes or test ids.
- **A bug fix** gets a regression test that fails without the fix, labelled `// Regression: …`.
- Tests must be deterministic. Inject `now` or stores instead of relying on timing.

Commands: `npm test` (all), `npm run test:unit` (`*.test.ts`), `npm run test:ui` (`*.test.tsx`),
`npm run test:coverage` (writes `coverage/`).

## Accessibility

- Every form control has a visible `<label>` (or `aria-label` for icon-only buttons). Errors link with
  `aria-describedby` and set `aria-invalid`.
- Use native elements first (`button`, `input type="radio"`); custom widgets follow WAI-ARIA patterns (see
  `components/ui/Tabs.tsx`, `Modal.tsx`).
- Keyboard: everything reachable and operable; visible focus; Escape closes overlays; focus returns to the trigger.
- Decorative icons get `aria-hidden="true"`. Status changes use `role="status"` or `role="alert"`.
- Check layouts at 390px and 1280px with no horizontal scroll.

## Dependencies

- Add a runtime dependency only when it removes real complexity or risk, and say why in the change.
  Prefer small, maintained, tree-shakeable packages (for example `zod/mini` over full `zod`).
- Run `npm audit` after any dependency change, and report the bundle-size impact of runtime additions.
- Keep `package-lock.json` committed.

## Honesty in the product

- Never present simulated agent activity, test results, builds, deployments, users, or metrics as real.
- New capabilities update `services/capabilities.ts` and the UI labels in the same change.
- Sample data is visibly labelled and read-only.

## Reviews

Each change description states what changed and why, how it was verified (commands run and results), any
behaviour change visible to users, and anything left undone. Reviewers check boundaries, error paths, tests at
the right layer, accessibility, and that no claims exceed what was verified.

## Adding a feature

1. Model new data in `domain/` (schema, rules, tests).
2. Extend or add a contract in `services/contracts/`, and extend the contract suite.
3. Implement adapters and wire them in `app/composition/`.
4. Build the UI in `features/<name>/`, using `useServices()` and `useAsyncData()`.
5. Add route-level tests for the main flow and failure states.
6. Update `capabilities.ts`, the docs, and `BACKEND_CONTRACTS.md` if the API changes.

## Adding an AI agent (backend)

1. Define its role in `AGENT_ROLES`, versioned instructions, input and output schemas, and tool allow-list in
   the backend registry.
2. Agents communicate through the orchestrator's typed task records, never by calling each other directly.
3. Every tool call is checked against the agent's permissions and written to the audit trail.
4. Output is validated against its schema before anything consumes it. Invalid output is a failed attempt.
5. Define retry, cancellation, and approval-gate behaviour before enabling the agent.
6. Add evaluation fixtures (representative inputs with expected properties of the output) alongside unit tests.

## Generated code and untrusted input

- Treat all model output, generated code, reference websites, and uploaded files as untrusted.
- Generated code runs only in ephemeral, resource-limited sandboxes with default-deny network egress, no
  production credentials, and no access to other tenants. Never on the API host or in a developer's shell.
- Reference URLs are fetched only by a sandboxed browser with SSRF protection (block private ranges and
  metadata endpoints).
- Never render generated HTML in the app's origin. Previews must use an isolated origin or a sandboxed iframe.
- File paths from models are normalised and confined to the project root.

## Backend (Python)

- Python 3.12, strict layering: `api/` (HTTP only) → `services/` (one transaction per use case) → `repositories/`
  (SQL only) and `domain/` (pure rules, no FastAPI, SQLAlchemy, or provider imports). Agents call `llm/` interfaces only.
- Domain rules shared with the frontend (`domain/projects.py`) keep the same messages as `src/domain/projects/*`.
  Change both together, along with the parity tests.
- Every schema change is a new Alembic revision; never edit an applied one. `alembic check` must pass.
- Raise `ApiError(code, safe_message, details=…)` from services. Codes must exist in `src/domain/errors.ts`.
- State changes go through `services/runs.transition()` under the run row lock, and append their event in the
  same transaction.
- Commands a client may retry must be idempotent (keys, unique constraints, or same-decision replay).
- Work that leaves the request (model calls, future tools) runs in the worker. Results commit only under a valid
  lease; document delivery semantics honestly (at-least-once, never "exactly-once").
- Model output is untrusted: validate shape and semantics before persisting, and persist every attempt.
- Database tests run against real PostgreSQL (`OMNIORA_TEST_DATABASE_URL`). Never substitute SQLite, and never
  report skipped database tests as passed.
- Gate: `ruff check`, `ruff format --check`, `pytest`, and `pip-audit` must pass.
