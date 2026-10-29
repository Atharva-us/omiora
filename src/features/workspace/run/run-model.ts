import type { BadgeTone } from '@/components/ui/Badge';
import type { AgentRole } from '@/domain/engineering/types';
import type { RunEvent, RunState } from '@/domain/runs/run';

export const RUN_STATE_META: Record<RunState, { label: string; tone: BadgeTone; description: string }> = {
  queued: { label: 'Queued', tone: 'info', description: 'Waiting for a worker to start planning.' },
  planning: { label: 'Planning', tone: 'info', description: 'The Project Manager agent is drafting a plan.' },
  'awaiting-approval': {
    label: 'Awaiting approval',
    tone: 'warning',
    description: 'Review the plan. Nothing happens until you decide.',
  },
  approved: {
    label: 'Approved',
    tone: 'success',
    description: 'You approved this plan. No code has been written: later agents are not built yet.',
  },
  rejected: { label: 'Rejected', tone: 'neutral', description: 'You rejected this plan.' },
  failed: { label: 'Failed', tone: 'danger', description: 'Planning did not produce a valid plan.' },
  cancelled: { label: 'Cancelled', tone: 'neutral', description: 'This run was cancelled.' },
};

export const AGENT_LABELS: Record<AgentRole, string> = {
  'project-manager': 'Project Manager',
  'requirements-analyst': 'Requirements Analyst',
  'reference-design': 'Reference & Design',
  'software-architect': 'Software Architect',
  'frontend-engineer': 'Frontend Engineer',
  'backend-engineer': 'Backend Engineer',
  'mobile-engineer': 'Mobile App Engineer',
  'database-engineer': 'Database Engineer',
  'qa-debugging': 'QA & Debugging',
  'security-release': 'Security & Release',
};

const str = (value: unknown) => (typeof value === 'string' || typeof value === 'number' ? String(value) : '?');

/** Human-readable text for a persisted run event. Unknown types are shown verbatim, never invented. */
export function describeRunEvent(event: RunEvent): string {
  const { data } = event;
  switch (event.type) {
    case 'run.created':
      return 'Planning run created';
    case 'run.state-changed':
      return `State changed: ${str(data.from)} → ${str(data.to)}`;
    case 'attempt.started':
      return `Project Manager attempt ${str(data.attempt)} started`;
    case 'attempt.finished':
      return `Attempt ${str(data.attempt)} finished: ${str(data.outcome)}`;
    case 'plan.created':
      return `Plan v${str(data.plan_version)} created with ${str(data.task_count)} proposed tasks`;
    case 'approval.requested':
      return `Approval requested for plan v${str(data.plan_version)}`;
    case 'approval.decided':
      return `Decision on plan v${str(data.plan_version)}: ${str(data.decision)}`;
    default:
      return event.type;
  }
}

/** A key reused across retries of the same "start" click, so a retried request cannot start two runs. */
export function newIdempotencyKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return `start-${Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')}`;
}
