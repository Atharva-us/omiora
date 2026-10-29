import type { Approval, ApprovalDecision, Run, RunDetail, RunEvent, RunState } from '@/domain/runs/run';

export type RunStreamStatus = 'connecting' | 'open' | 'reconnecting' | 'closed';

export interface RunStreamHandlers {
  onEvent: (event: RunEvent) => void;
  onStatus: (status: RunStreamStatus) => void;
  /** The run reached a terminal state and the server closed the stream. */
  onEnd: (state: RunState) => void;
}

export interface DecisionInput {
  decision: ApprovalDecision;
  /** Must match the approval's plan version; a stale version is rejected with `conflict`. */
  planVersion: number;
  comment?: string;
}

/**
 * Project Manager planning runs.
 *
 * Events are notifications, and `getRun` is the source of truth: clients
 * re-fetch the run detail after events or reconnects to reconcile state.
 * Failures are `AppError`s (`not-found`, `conflict`, `rate-limited`,
 * `provider-not-configured`, `unauthenticated`, `network`).
 */
export interface RunService {
  /** False when runs cannot work in this mode (demo). The UI explains why instead of offering actions. */
  readonly available: boolean;
  listRuns(projectId: string): Promise<Run[]>;
  getRun(runId: string): Promise<RunDetail>;
  /**
   * Reusing an idempotency key returns the original run instead of starting another. Planning
   * follows the project's approved requirements; `withoutRequirements` is the explicit, recorded
   * choice to skip them (otherwise a project without approved requirements gets `conflict`).
   */
  startPlanning(projectId: string, idempotencyKey: string, options?: { withoutRequirements?: boolean }): Promise<Run>;
  cancel(runId: string): Promise<Run>;
  decide(runId: string, approvalId: string, input: DecisionInput): Promise<Approval>;
  listEvents(runId: string, afterSeq: number): Promise<RunEvent[]>;
  /** Streams events after `afterSeq`, reconnecting and resuming automatically. Returns an unsubscribe function. */
  subscribe(runId: string, afterSeq: number, handlers: RunStreamHandlers): () => void;
}
