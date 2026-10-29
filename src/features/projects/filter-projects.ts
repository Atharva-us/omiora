import { technologyNames } from '@/domain/projects/catalog';
import {
  PLATFORM_TARGETS,
  PROJECT_STATUSES,
  projectTechnologies,
  type PlatformTarget,
  type Project,
  type ProjectStatus,
} from '@/domain/projects/project';

export type PlatformFilter = PlatformTarget | 'all';
export type StatusFilter = ProjectStatus | 'all';
export type SortOrder = 'updated' | 'name';

export interface ProjectFilters {
  query: string;
  platform: PlatformFilter;
  status: StatusFilter;
  sort: SortOrder;
}

export const DEFAULT_FILTERS: ProjectFilters = { query: '', platform: 'all', status: 'all', sort: 'updated' };

const PLATFORM_FILTERS: readonly PlatformFilter[] = ['all', ...PLATFORM_TARGETS];
const STATUS_FILTERS: readonly StatusFilter[] = ['all', ...PROJECT_STATUSES];
const SORT_ORDERS: readonly SortOrder[] = ['updated', 'name'];

/** Narrows an untrusted string (URL parameter, <select> value) to an allowed value. */
function pick<T extends string>(value: string | null, allowed: readonly T[], fallback: T): T {
  return allowed.find((candidate) => candidate === value) ?? fallback;
}

export const parsePlatformFilter = (value: string | null) => pick(value, PLATFORM_FILTERS, DEFAULT_FILTERS.platform);
export const parseStatusFilter = (value: string | null) => pick(value, STATUS_FILTERS, DEFAULT_FILTERS.status);
export const parseSortOrder = (value: string | null) => pick(value, SORT_ORDERS, DEFAULT_FILTERS.sort);

export function filtersFromSearchParams(params: URLSearchParams): ProjectFilters {
  return {
    query: params.get('q') ?? DEFAULT_FILTERS.query,
    platform: parsePlatformFilter(params.get('platform')),
    status: parseStatusFilter(params.get('status')),
    sort: parseSortOrder(params.get('sort')),
  };
}

/** Only non-default values are written, keeping URLs short and shareable. */
export function filtersToSearchParams(filters: ProjectFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.query) params.set('q', filters.query);
  if (filters.platform !== DEFAULT_FILTERS.platform) params.set('platform', filters.platform);
  if (filters.status !== DEFAULT_FILTERS.status) params.set('status', filters.status);
  if (filters.sort !== DEFAULT_FILTERS.sort) params.set('sort', filters.sort);
  return params;
}

export function filterProjects(projects: readonly Project[], filters: ProjectFilters): Project[] {
  const query = filters.query.trim().toLowerCase();
  const matches = projects.filter((project) => {
    const { configuration } = project;
    if (filters.platform !== 'all' && configuration.platform !== filters.platform) return false;
    if (filters.status !== 'all' && project.status !== filters.status) return false;
    if (!query) return true;
    const haystack = [configuration.name, configuration.description, ...technologyNames(projectTechnologies(project))]
      .join(' ')
      .toLowerCase();
    return haystack.includes(query);
  });
  return matches.sort((a, b) =>
    filters.sort === 'name'
      ? a.configuration.name.localeCompare(b.configuration.name)
      : b.updatedAt.localeCompare(a.updatedAt),
  );
}

export function hasActiveFilters(filters: ProjectFilters): boolean {
  return filters.query.trim() !== '' || filters.platform !== 'all' || filters.status !== 'all';
}
