import { useId, type ReactNode } from 'react';
import { ChevronDown, Search, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { PLATFORM_LABELS } from '@/domain/projects/catalog';
import { PROJECT_STATUS_META } from '@/components/project/project-status-meta';
import { PLATFORM_TARGETS, type ProjectStatus } from '@/domain/projects/project';
import {
  hasActiveFilters,
  parsePlatformFilter,
  parseSortOrder,
  parseStatusFilter,
  type ProjectFilters,
} from './filter-projects';

interface ProjectFiltersBarProps {
  filters: ProjectFilters;
  onChange: (filters: ProjectFilters) => void;
  onClear: () => void;
}

interface SelectProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}

function Select({ label, value, onChange, children }: SelectProps) {
  const id = useId();
  return (
    <div className="relative min-w-36 flex-1 sm:flex-none">
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 w-full appearance-none rounded-md border border-line bg-surface pr-9 pl-3 text-sm text-ink focus:border-cyan/70 focus:ring-2 focus:ring-cyan/40 focus:outline-none sm:w-44"
      >
        {children}
      </select>
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-faint"
      />
    </div>
  );
}

const STATUS_OPTIONS: ProjectStatus[] = ['configured', 'draft', 'generating', 'testing', 'ready', 'failed'];

export function ProjectFiltersBar({ filters, onChange, onClear }: ProjectFiltersBarProps) {
  const searchId = useId();
  return (
    <div role="search" className="flex flex-col gap-3 lg:flex-row lg:items-center">
      <div className="relative flex-1">
        <label htmlFor={searchId} className="sr-only">
          Search projects
        </label>
        <Search aria-hidden="true" className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-faint" />
        <input
          id={searchId}
          type="search"
          value={filters.query}
          onChange={(event) => onChange({ ...filters, query: event.target.value })}
          placeholder="Search by name, description, or technology"
          className="h-10 w-full rounded-md border border-line bg-surface pr-3 pl-9 text-sm text-ink placeholder:text-faint focus:border-cyan/70 focus:ring-2 focus:ring-cyan/40 focus:outline-none"
        />
      </div>
      <div className="flex flex-wrap gap-3">
        <Select
          label="Filter by platform"
          value={filters.platform}
          onChange={(value) => onChange({ ...filters, platform: parsePlatformFilter(value) })}
        >
          <option value="all">All platforms</option>
          {PLATFORM_TARGETS.map((platform) => (
            <option key={platform} value={platform}>
              {PLATFORM_LABELS[platform]}
            </option>
          ))}
        </Select>
        <Select
          label="Filter by status"
          value={filters.status}
          onChange={(value) => onChange({ ...filters, status: parseStatusFilter(value) })}
        >
          <option value="all">All statuses</option>
          {STATUS_OPTIONS.map((status) => (
            <option key={status} value={status}>
              {PROJECT_STATUS_META[status].label}
            </option>
          ))}
        </Select>
        <Select
          label="Sort projects"
          value={filters.sort}
          onChange={(value) => onChange({ ...filters, sort: parseSortOrder(value) })}
        >
          <option value="updated">Recently updated</option>
          <option value="name">Name (A–Z)</option>
        </Select>
        {hasActiveFilters(filters) && (
          <Button variant="ghost" onClick={onClear}>
            <X aria-hidden="true" />
            Clear
          </Button>
        )}
      </div>
    </div>
  );
}
