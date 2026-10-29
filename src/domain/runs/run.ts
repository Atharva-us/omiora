import { z } from 'zod/mini';
import { AGENT_ROLES } from '@/domain/engineering/types';
import { technologyIdSchema } from '@/domain/projects/project';

/**
 * Agent runs, plans, approvals, and run events. Mirrors the backend's
 * `domain/runs.py` and `api/schemas.py`. Every API response is parsed with
 * these schemas before the UI sees it.
 */

export const RUN_STATES = [
  'queued',
  'planning',
  'awaiting-approval',
  'approved',
  'rejected',
  'failed',
  'cancelled',
] as const;
export const runStateSchema = z.enum(RUN_STATES);
export type RunState = z.infer<typeof runStateSchema>;

export const TERMINAL_RUN_STATES: readonly RunState[] = ['approved', 'rejected', 'failed', 'cancelled'];
export const isTerminalRunState = (state: RunState) => TERMINAL_RUN_STATES.includes(state);

const timestamp = z.iso.datetime();
const id = z.string().check(z.minLength(1));

export const runSchema = z.object({
  id,
  projectId: id,
  agentRole: z.string(),
  state: runStateSchema,
  currentPlanVersion: z.nullable(z.int()),
  failureCode: z.nullable(z.string()),
  failureMessage: z.nullable(z.string()),
  lastEventSeq: z.int(),
  /** The approved requirements version this plan must follow, or null when planned without requirements. */
  pinnedRequirementsVersionId: z.nullable(z.string()),
  /** True when the user explicitly chose to plan without approved requirements. */
  requirementsSkipped: z.boolean(),
  createdAt: timestamp,
  updatedAt: timestamp,
});
export type Run = z.infer<typeof runSchema>;

export const planContentSchema = z.object({
  summary: z.string(),
  requirements: z.array(
    z.object({
      id: z.string(),
      statement: z.string(),
      kind: z.enum(['functional', 'non-functional', 'constraint']),
      priority: z.enum(['must', 'should', 'could']),
      source: z.enum(['user', 'inferred']),
    }),
  ),
  assumptions: z.array(z.string()),
  openQuestions: z.array(
    z.object({ id: z.string(), question: z.string(), whyItMatters: z.string(), blocking: z.boolean() }),
  ),
  recommendedStack: z.object({ technologies: z.array(technologyIdSchema), rationale: z.string() }),
  requiredApprovals: z.array(z.object({ gate: z.enum(['plan', 'architecture', 'release']), description: z.string() })),
  /** Approved must-have requirements the plan deliberately leaves uncovered, with the reason. */
  flaggedRequirements: z.array(z.object({ id: z.string(), reason: z.string() })),
});
export type PlanContent = z.infer<typeof planContentSchema>;

export const planSchema = z.object({ version: z.int(), createdAt: timestamp, content: planContentSchema });
export type Plan = z.infer<typeof planSchema>;

/** Agents 2–10: the Project Manager proposes work for them but never assigns work to itself. */
const futureAgentSchema = z.enum(AGENT_ROLES.filter((role) => role !== 'project-manager'));

export const planTaskSchema = z.object({
  key: z.string(),
  title: z.string(),
  description: z.string(),
  acceptanceCriteria: z.array(z.string()),
  dependsOn: z.array(z.string()),
  requirementIds: z.array(z.string()),
  suggestedAgent: futureAgentSchema,
  /** Proposed tasks only: nothing has been executed. */
  status: z.literal('proposed'),
});
export type PlanTask = z.infer<typeof planTaskSchema>;

export const APPROVAL_STATUSES = [
  'pending',
  'approved',
  'rejected',
  'revision-requested',
  'superseded',
  'cancelled',
] as const;

export const approvalSchema = z.object({
  id,
  planVersion: z.int(),
  gate: z.string(),
  status: z.enum(APPROVAL_STATUSES),
  comment: z.nullable(z.string()),
  decidedAt: z.nullable(timestamp),
  createdAt: timestamp,
});
export type Approval = z.infer<typeof approvalSchema>;

export const attemptSchema = z.object({
  attempt: z.int(),
  planVersion: z.int(),
  outcome: z.enum(['succeeded', 'invalid-output', 'provider-error']),
  provider: z.string(),
  model: z.string(),
  inputTokens: z.nullable(z.int()),
  outputTokens: z.nullable(z.int()),
  latencyMs: z.nullable(z.int()),
  errorCode: z.nullable(z.string()),
  errorMessage: z.nullable(z.string()),
  validationErrors: z.array(z.string()),
  createdAt: timestamp,
});
export type Attempt = z.infer<typeof attemptSchema>;

export const runDetailSchema = z.object({
  run: runSchema,
  plan: z.nullable(planSchema),
  tasks: z.array(planTaskSchema),
  approvals: z.array(approvalSchema),
  attempts: z.array(attemptSchema),
  /** The pinned approved requirements version (Agent 2), if this plan follows one. */
  requirements: z.nullable(
    z.object({ versionId: z.string(), sessionId: z.string(), version: z.int(), contentSha256: z.string() }),
  ),
});
export type RunDetail = z.infer<typeof runDetailSchema>;

export const RUN_EVENT_TYPES = [
  'run.created',
  'run.state-changed',
  'attempt.started',
  'attempt.finished',
  'plan.created',
  'approval.requested',
  'approval.decided',
  // Requirements Analyst sessions share the run event stream.
  'turn.queued',
  'turn.completed',
  'turn.failed',
  'answers.submitted',
  'requirements.version-created',
] as const;

export const runEventSchema = z.object({
  seq: z.int(),
  type: z.string(),
  data: z.record(z.string(), z.unknown()),
  at: timestamp,
});
export type RunEvent = z.infer<typeof runEventSchema>;

export type ApprovalDecision = 'approve' | 'reject' | 'revise';

/** The approval a user can act on: pending and for the plan currently shown. */
export function pendingApproval(detail: RunDetail): Approval | null {
  const current = detail.run.currentPlanVersion;
  return detail.approvals.find((approval) => approval.status === 'pending' && approval.planVersion === current) ?? null;
}
