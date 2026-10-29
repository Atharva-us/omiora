import { Link } from 'react-router-dom';
import { ChevronLeft } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { PLATFORM_LABELS } from '@/domain/projects/catalog';
import { PROJECT_STATUS_META } from '@/components/project/project-status-meta';
import { ProjectStatusBadge } from '@/components/project/ProjectStatusBadge';
import type { Project } from '@/domain/projects/project';

export function ProjectSummary({ project }: { project: Project }) {
  return (
    <div>
      <Link to="/projects" className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink">
        <ChevronLeft aria-hidden="true" className="size-3.5" />
        All projects
      </Link>
      <h1 className="mt-3 text-lg leading-snug font-semibold break-words text-ink">{project.configuration.name}</h1>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <ProjectStatusBadge status={project.status} />
        {project.source === 'sample' && <Badge tone="warning">Sample · read-only</Badge>}
        <span className="text-xs text-faint">{PLATFORM_LABELS[project.configuration.platform]}</span>
      </div>
      <p className="mt-3 text-xs leading-relaxed text-faint">{PROJECT_STATUS_META[project.status].description}</p>
    </div>
  );
}
