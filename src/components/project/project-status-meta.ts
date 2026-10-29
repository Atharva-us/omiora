import type { ProjectStatus } from '@/domain/projects/project';

import type { BadgeTone } from '@/components/ui/Badge';

export const PROJECT_STATUS_META: Record<ProjectStatus, { label: string; tone: BadgeTone; description: string }> = {
  draft: { label: 'Draft', tone: 'neutral', description: 'Configuration incomplete.' },
  configured: {
    label: 'Configured',
    tone: 'info',
    description: 'Configuration saved. Generation has not started because the AI engine is not yet connected.',
  },
  queued: { label: 'Queued', tone: 'info', description: 'Waiting for an engine worker.' },
  planning: { label: 'Planning', tone: 'info', description: 'Requirements are being analysed.' },
  generating: { label: 'Generating', tone: 'info', description: 'Source code is being written.' },
  testing: { label: 'Testing', tone: 'info', description: 'Automated tests are running.' },
  repairing: { label: 'Repairing', tone: 'warning', description: 'Failures are being repaired.' },
  ready: { label: 'Ready', tone: 'success', description: 'Build and tests passed.' },
  failed: { label: 'Failed', tone: 'danger', description: 'The last run failed.' },
};
