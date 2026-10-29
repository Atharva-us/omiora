import type { BadgeTone } from '@/components/ui/Badge';
import type { AnswerInput, AnswerValue, Question, SessionState } from '@/domain/requirements/requirements';

export const SESSION_STATE_META: Record<SessionState, { label: string; tone: BadgeTone; description: string }> = {
  queued: { label: 'Queued', tone: 'info', description: 'Waiting for a worker to start the Requirements Analyst.' },
  discovering: {
    label: 'Discovering',
    tone: 'info',
    description: 'The analyst asks questions and keeps a versioned list of requirements.',
  },
  'ready-for-review': {
    label: 'Ready for review',
    tone: 'warning',
    description: 'The analyst found no blocking gaps. Review the requirements, then submit them for approval.',
  },
  'awaiting-approval': {
    label: 'Awaiting approval',
    tone: 'warning',
    description: 'This version is frozen. Approve it or request changes.',
  },
  approved: {
    label: 'Approved',
    tone: 'success',
    description: 'These requirements are approved and immutable. The Project Manager plans from this exact version.',
  },
  'needs-changes': {
    label: 'Needs changes',
    tone: 'warning',
    description: 'You requested changes. The analyst is revising the requirements.',
  },
  failed: { label: 'Failed', tone: 'danger', description: 'This session stopped because of a problem it cannot recover from.' },
  cancelled: { label: 'Cancelled', tone: 'neutral', description: 'This session was cancelled.' },
};

export const SOURCE_LABELS = {
  brief: 'From the brief',
  note: 'From a note',
  answer: 'From your answer',
  inferred: 'Inferred by the analyst',
} as const;

export interface AnswerDraft {
  value: AnswerValue | undefined;
  unknown: boolean;
}

export type AnswerDrafts = Record<string, AnswerDraft>;

/** Drafts start from what the server recorded, so a refresh shows the saved answers. */
export function initialDrafts(questions: readonly Question[]): AnswerDrafts {
  const drafts: AnswerDrafts = {};
  for (const question of questions) {
    if (question.answer) drafts[question.key] = { value: question.answer.value, unknown: question.answer.unknown };
  }
  return drafts;
}

function isComplete(question: Question, draft: AnswerDraft): boolean {
  if (draft.unknown) return true;
  const { value } = draft;
  switch (question.kind) {
    case 'single-choice':
      return typeof value === 'string' && question.options.includes(value);
    case 'multiple-choice':
      return Array.isArray(value) && value.length > 0;
    case 'yes-no':
      return typeof value === 'boolean';
    case 'free-text':
      return typeof value === 'string' && value.trim().length > 0;
  }
}

function sameAnswer(question: Question, draft: AnswerDraft): boolean {
  const saved = question.answer;
  if (!saved) return false;
  if (saved.unknown || draft.unknown) return saved.unknown === draft.unknown;
  return JSON.stringify(saved.value) === JSON.stringify(draft.value);
}

/** Complete answers that differ from what the server has. Unchanged and half-filled drafts are not sent. */
export function changedAnswers(questions: readonly Question[], drafts: AnswerDrafts): AnswerInput[] {
  const answers: AnswerInput[] = [];
  for (const question of questions) {
    const draft = drafts[question.key];
    if (question.status === 'withdrawn' || !draft || !isComplete(question, draft) || sameAnswer(question, draft)) continue;
    answers.push(draft.unknown ? { questionKey: question.key, unknown: true } : { questionKey: question.key, value: draft.value ?? null });
  }
  return answers;
}

/** A key reused across retries of the same submission, so a retried request cannot apply twice. */
export function newSubmissionKey(prefix: string): string {
  const bytes = crypto.getRandomValues(new Uint8Array(12));
  return `${prefix}-${Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')}`;
}
