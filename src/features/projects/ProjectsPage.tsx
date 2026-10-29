import { useCallback, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { FolderPlus, Plus, SearchX } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button, ButtonLink } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { LoadErrorNotice } from '@/components/feedback/LoadErrorNotice';
import { Notice } from '@/components/ui/Notice';
import { LoadingBlock } from '@/components/ui/Spinner';
import { useAsyncData } from '@/hooks/use-async-data';
import { useServices } from '@/hooks/use-services';
import type { Project } from '@/domain/projects/project';
import {
  filterProjects,
  filtersFromSearchParams,
  filtersToSearchParams,
  hasActiveFilters,
  type ProjectFilters,
} from './filter-projects';
import { ProjectCard } from './ProjectCard';
import { ProjectFiltersBar } from './ProjectFiltersBar';

function ProjectGrid({ projects }: { projects: Project[] }) {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {projects.map((project) => (
        <li key={project.id} className="flex">
          <div className="flex w-full flex-col [&>article]:flex-1">
            <ProjectCard project={project} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function ProjectsPage() {
  const { projects: projectService, mode } = useServices();
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = filtersFromSearchParams(searchParams);
  const [showSamples, setShowSamples] = useState(true);

  const loadAll = useCallback(
    () => Promise.all([projectService.listProjects(), projectService.listSampleProjects()]),
    [projectService],
  );
  const { data, errorMessage, errorCode, isLoading, reload } = useAsyncData(loadAll, 'projects.load-failed');
  const [userProjects, sampleProjects] = data ?? [[], []];

  const visibleUser = filterProjects(userProjects, filters);
  const visibleSamples = filterProjects(sampleProjects, filters);

  const updateFilters = (next: ProjectFilters) => setSearchParams(filtersToSearchParams(next), { replace: true });
  const clearFilters = () => setSearchParams(new URLSearchParams(), { replace: true });
  const filtering = hasActiveFilters(filters);

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 sm:py-12 lg:px-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-[-0.025em]">Projects</h1>
          <p className="mt-1.5 text-sm text-muted">Configure, open, and manage your software projects.</p>
        </div>
        <ButtonLink to="/new" className="self-start sm:self-auto">
          <Plus aria-hidden="true" />
          New Project
        </ButtonLink>
      </div>

      {mode === 'demo' && (
        <Notice tone="info" className="mt-8">
          Projects are saved in this browser using demo storage. Accounts and cloud sync are not connected in demo
          mode, so projects will not appear on other devices.
        </Notice>
      )}

      <div className="mt-8">
        <ProjectFiltersBar filters={filters} onChange={updateFilters} onClear={clearFilters} />
      </div>

      {errorMessage ? (
        <LoadErrorNotice
          className="mt-8"
          title="Projects could not be loaded"
          message={errorMessage}
          code={errorCode}
          onRetry={reload}
        />
      ) : isLoading && !data ? (
        <LoadingBlock label="Loading projects" />
      ) : (
        <>
          <section aria-labelledby="your-projects" className="mt-10">
            <div className="mb-4 flex items-baseline justify-between">
              <h2 id="your-projects" className="text-sm font-semibold text-ink">
                Your projects
                <span className="ml-2 font-mono text-xs font-normal text-faint">{visibleUser.length}</span>
              </h2>
            </div>
            {userProjects.length === 0 ? (
              <div className="rounded-lg border border-dashed border-line">
                <EmptyState
                  icon={FolderPlus}
                  title="No projects yet"
                  action={
                    <ButtonLink to="/new">
                      <Plus aria-hidden="true" />
                      Create your first project
                    </ButtonLink>
                  }
                >
                  Describe what you want to build and configure its platform, stack, and requirements.
                </EmptyState>
              </div>
            ) : visibleUser.length === 0 ? (
              <div className="rounded-lg border border-dashed border-line">
                <EmptyState
                  icon={SearchX}
                  title="No projects match your filters"
                  action={
                    <Button variant="secondary" onClick={clearFilters}>
                      Clear filters
                    </Button>
                  }
                />
              </div>
            ) : (
              <ProjectGrid projects={visibleUser} />
            )}
          </section>

          <section aria-labelledby="sample-projects" className="mt-14">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2">
                <h2 id="sample-projects" className="text-sm font-semibold text-ink">
                  Sample projects
                </h2>
                <Badge tone="warning">Demo data</Badge>
              </div>
              <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-muted">
                <input
                  type="checkbox"
                  checked={showSamples}
                  onChange={(event) => setShowSamples(event.target.checked)}
                  className="size-4 rounded border-line accent-cyan"
                />
                Show sample projects
              </label>
            </div>
            {showSamples && (
              <>
                <p className="mb-4 text-sm text-faint">
                  Illustrative configurations for exploring the interface. They are not your projects and were not
                  generated by Omniora.
                </p>
                {visibleSamples.length > 0 ? (
                  <ProjectGrid projects={visibleSamples} />
                ) : (
                  <p className="text-sm text-faint">
                    {filtering ? 'No sample projects match your filters.' : 'No sample projects available.'}
                  </p>
                )}
              </>
            )}
          </section>
        </>
      )}
    </div>
  );
}
