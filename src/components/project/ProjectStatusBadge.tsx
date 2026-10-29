import { Badge } from '@/components/ui/Badge';
import { PROJECT_STATUS_META } from './project-status-meta';
import type { ProjectStatus } from '@/domain/projects/project';

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  const meta = PROJECT_STATUS_META[status];
  return (
    <span title={meta.description}>
      <Badge tone={meta.tone} dot>
        {meta.label}
      </Badge>
    </span>
  );
}
