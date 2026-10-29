import type {
  AnswerInput,
  ApprovedRequirements,
  RequirementsDecision,
  RequirementsSession,
  RequirementsVersion,
  SessionDetail,
  VersionSummary,
} from '@/domain/requirements/requirements';

/**
 * Requirements Analyst (Agent 2) discovery sessions.
 *
 * A session id is also a run id: live progress arrives through `RunService.subscribe`, and
 * `getSession` is the source of truth to re-fetch after each event. Failures are `AppError`s
 * (`not-found`, `conflict`, `validation`, `rate-limited`, `provider-not-configured`,
 * `unauthenticated`, `network`).
 */
export interface RequirementsService {
  /** False when discovery cannot work in this mode (demo). The UI explains why instead of offering actions. */
  readonly available: boolean;
  listSessions(projectId: string): Promise<RequirementsSession[]>;
  getSession(sessionId: string): Promise<SessionDetail>;
  /** Reusing an idempotency key returns the original session instead of starting another. */
  startSession(projectId: string, idempotencyKey: string): Promise<RequirementsSession>;
  /** Saves answers; `advance` asks the analyst for the next turn. Replaying a key applies nothing twice. */
  submitAnswers(sessionId: string, idempotencyKey: string, answers: AnswerInput[], advance: boolean): Promise<SessionDetail>;
  retryTurn(sessionId: string): Promise<SessionDetail>;
  submitForApproval(sessionId: string, version: number): Promise<SessionDetail>;
  decide(
    sessionId: string,
    approvalId: string,
    input: { decision: RequirementsDecision; version: number; comment?: string },
  ): Promise<SessionDetail>;
  cancel(sessionId: string): Promise<SessionDetail>;
  listVersions(sessionId: string): Promise<VersionSummary[]>;
  getVersion(sessionId: string, version: number, diffFrom?: number): Promise<RequirementsVersion>;
  /** The project's latest approved requirements, or null when none are approved yet. */
  getApproved(projectId: string): Promise<ApprovedRequirements | null>;
}
