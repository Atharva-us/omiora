import { Link } from 'react-router-dom';
import { ArrowUpRight, Globe, MonitorSmartphone, Smartphone } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { PLATFORM_LABELS, technologyNames } from '@/domain/projects/catalog';
import { formatDate } from '@/lib/format';
import { projectTechnologies, type Project } from '@/domain/projects/project';
import { ProjectStatusBadge } from '@/components/project/ProjectStatusBadge';

const platformIcons = { website: Globe, mobile: Smartphone, both: MonitorSmartphone };

export function ProjectCard({ project }: { project: Project }) {
  const { configuration } = project;
  const PlatformIcon = platformIcons[configuration.platform];
  const names = technologyNames(projectTechnologies(project));
  return (
    <article className="group relative flex flex-col rounded-lg border border-line bg-surface p-5 transition-colors hover:border-[#33415a]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-[0.9375rem] font-semibold text-ink">
            <Link
              to={`/projects/${project.id}`}
              className="after:absolute after:inset-0 after:rounded-lg focus-visible:outline-none"
              aria-label={`Open project ${configuration.name}`}
            >
              {configuration.name}
            </Link>
          </h3>
          <p className="mt-1 flex items-center gap-1.5 text-xs text-faint">
            <PlatformIcon aria-hidden="true" className="size-3.5" />
            {PLATFORM_LABELS[configuration.platform]}
          </p>
        </div>
        <ArrowUpRight
          aria-hidden="true"
          className="size-4 shrink-0 text-faint transition-colors group-hover:text-cyan"
        />
      </div>

      <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-muted">{configuration.description}</p>

      <div className="mt-4 flex flex-wrap gap-1.5">
        {names.length > 0 ? (
          names.map((name) => <Badge key={name}>{name}</Badge>)
        ) : (
          <span className="text-xs text-faint">Stack: recommendation requested</span>
        )}
      </div>

      <div aria-hidden="true" className="min-h-5 flex-1" />
      <div className="flex items-center justify-between gap-3 border-t border-line-soft pt-4">
        <ProjectStatusBadge status={project.status} />
        <span className="text-xs text-faint">
          {project.source === 'sample' ? 'Sample' : 'Updated'}{' '}
          <time dateTime={project.updatedAt}>{formatDate(project.updatedAt)}</time>
        </span>
      </div>
    </article>
  );
}
