import { z } from 'zod/mini';

/**
 * Requirements Analyst (Agent 2) sessions, questions, and versioned requirements. Mirrors the
 * backend's `domain/requirements.py` and `api/schemas.py`. Every API response is parsed with these
 * schemas before the UI sees it.
 */

export const SESSION_STATES = [
  'queued',
  'discovering',
  'ready-for-review',
  'awaiting-approval',
  'approved',
  'needs-changes',
  'failed',
  'cancelled',
] as const;
export const sessionStateSchema = z.enum(SESSION_STATES);
export type SessionState = z.infer<typeof sessionStateSchema>;

export const TERMINAL_SESSION_STATES: readonly SessionState[] = ['approved', 'failed', 'cancelled'];
export const isTerminalSessionState = (state: SessionState) => TERMINAL_SESSION_STATES.includes(state);

const timestamp = z.iso.datetime();
const id = z.string().check(z.minLength(1));

export const sessionSchema = z.object({
  id,
  projectId: id,
  state: sessionStateSchema,
  failureCode: z.nullable(z.string()),
  failureMessage: z.nullable(z.string()),
  lastEventSeq: z.int(),
  createdAt: timestamp,
  updatedAt: timestamp,
});
export type RequirementsSession = z.infer<typeof sessionSchema>;

export const PRIORITIES = ['must', 'should', 'could', 'wont'] as const;
export type Priority = (typeof PRIORITIES)[number];

export const requirementSchema = z.object({
  id: z.string(),
  statement: z.string(),
  kind: z.enum(['functional', 'non-functional', 'constraint']),
  priority: z.enum(PRIORITIES),
  confidence: z.enum(['high', 'medium', 'low']),
  source: z.enum(['brief', 'note', 'answer', 'inferred']),
  evidence: z.array(z.string()),
  acceptanceCriteria: z.array(z.string()),
  tags: z.array(z.string()),
  status: z.enum(['active', 'deprecated']),
  deprecationReason: z.string(),
});
export type Requirement = z.infer<typeof requirementSchema>;

export const documentSchema = z.object({
  schemaVersion: z.int(),
  context: z.object({
    goal: z.string(),
    scope: z.string(),
    platform: z.string(),
    deployment: z.string(),
    personas: z.array(z.object({ name: z.string(), description: z.string() })),
    tenancy: z.enum(['single', 'multi', 'unknown']),
    constraints: z.array(z.string()),
    integrations: z.array(z.string()),
    outOfScope: z.array(z.string()),
  }),
  requirements: z.array(requirementSchema),
  assumptions: z.array(
    z.object({ statement: z.string(), confidence: z.enum(['high', 'medium', 'low']), basis: z.array(z.string()) }),
  ),
  openQuestions: z.array(
    z.object({ key: z.string(), prompt: z.string(), blocking: z.boolean(), topic: z.string(), status: z.enum(['open', 'unknown']) }),
  ),
  readiness: z.object({ ready: z.boolean(), blockers: z.array(z.string()) }),
  decisions: z.array(z.string()),
});
export type RequirementsDocument = z.infer<typeof documentSchema>;

const summaryShape = {
  id,
  version: z.int(),
  parentVersionId: z.nullable(z.string()),
  contentSha256: z.string(),
  turnNumber: z.nullable(z.int()),
  createdAt: timestamp,
  frozenAt: z.nullable(timestamp),
  approvedAt: z.nullable(timestamp),
  requirementCount: z.int(),
  mustCount: z.int(),
  ready: z.boolean(),
};
export const versionSummarySchema = z.object(summaryShape);
export type VersionSummary = z.infer<typeof versionSummarySchema>;

export const versionDiffSchema = z.object({
  fromVersion: z.int(),
  added: z.array(z.string()),
  deprecated: z.array(z.string()),
  changed: z.array(z.object({ id: z.string(), fields: z.array(z.string()) })),
  contextFields: z.array(z.string()),
});
export type VersionDiff = z.infer<typeof versionDiffSchema>;

export const versionSchema = z.object({ ...summaryShape, content: documentSchema, diff: z.nullable(versionDiffSchema) });
export type RequirementsVersion = z.infer<typeof versionSchema>;

export const QUESTION_KINDS = ['single-choice', 'multiple-choice', 'free-text', 'yes-no'] as const;
export type QuestionKind = (typeof QUESTION_KINDS)[number];

export const answerValueSchema = z.union([z.string(), z.array(z.string()), z.boolean(), z.null()]);
export type AnswerValue = z.infer<typeof answerValueSchema>;

export const questionSchema = z.object({
  key: z.string(),
  turnNumber: z.int(),
  prompt: z.string(),
  why: z.string(),
  kind: z.enum(QUESTION_KINDS),
  options: z.array(z.string()),
  blocking: z.boolean(),
  topic: z.string(),
  relatesTo: z.array(z.string()),
  status: z.enum(['open', 'answered', 'withdrawn']),
  answer: z.nullable(z.object({ value: answerValueSchema, unknown: z.boolean(), answeredAt: timestamp })),
});
export type Question = z.infer<typeof questionSchema>;

export const turnSchema = z.object({
  number: z.int(),
  status: z.enum(['queued', 'running', 'completed', 'failed', 'cancelled']),
  trigger: z.string(),
  tries: z.int(),
  failureCode: z.nullable(z.string()),
  failureMessage: z.nullable(z.string()),
  requirementsVersion: z.nullable(z.int()),
  createdAt: timestamp,
  completedAt: z.nullable(timestamp),
});
export type Turn = z.infer<typeof turnSchema>;

export const requirementsApprovalSchema = z.object({
  id,
  version: z.int(),
  gate: z.string(),
  status: z.enum(['pending', 'approved', 'rejected', 'revision-requested', 'superseded', 'cancelled']),
  comment: z.nullable(z.string()),
  decidedAt: z.nullable(timestamp),
  createdAt: timestamp,
});
export type RequirementsApproval = z.infer<typeof requirementsApprovalSchema>;

export const turnAttemptSchema = z.object({
  turn: z.int(),
  attempt: z.int(),
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
export type TurnAttempt = z.infer<typeof turnAttemptSchema>;

export const sessionDetailSchema = z.object({
  session: sessionSchema,
  turn: z.nullable(turnSchema),
  maxTurns: z.int(),
  questions: z.array(questionSchema),
  version: z.nullable(versionSchema),
  approvals: z.array(requirementsApprovalSchema),
  attempts: z.array(turnAttemptSchema),
});
export type SessionDetail = z.infer<typeof sessionDetailSchema>;

export const approvedRequirementsSchema = z.object({ sessionId: id, version: versionSchema });
export type ApprovedRequirements = z.infer<typeof approvedRequirementsSchema>;

/** The analyst is working only when the server says a turn is queued or running. */
export function isAnalysing(detail: SessionDetail): boolean {
  return detail.turn !== null && (detail.turn.status === 'queued' || detail.turn.status === 'running');
}

export function pendingRequirementsApproval(detail: SessionDetail): RequirementsApproval | null {
  const current = detail.version?.version;
  return detail.approvals.find((a) => a.status === 'pending' && a.version === current) ?? null;
}

/** Active requirements grouped by priority, in priority order; deprecated ones are listed separately. */
export function groupByPriority(requirements: readonly Requirement[]): { priority: Priority; items: Requirement[] }[] {
  return PRIORITIES.map((priority) => ({
    priority,
    items: requirements.filter((r) => r.status === 'active' && r.priority === priority),
  })).filter((group) => group.items.length > 0);
}

export interface AnswerInput {
  questionKey: string;
  value?: AnswerValue;
  unknown?: boolean;
}

export type RequirementsDecision = 'approve' | 'request-changes';
