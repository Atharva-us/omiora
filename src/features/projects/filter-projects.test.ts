import { describe, expect, it } from 'vitest';
import type { Project } from '@/domain/projects/project';
import { validConfiguration } from '@/test/fixtures';
import {
  DEFAULT_FILTERS,
  filterProjects,
  filtersFromSearchParams,
  filtersToSearchParams,
  parsePlatformFilter,
} from './filter-projects';

const makeProject = (id: string, name: string, updatedAt: string, overrides: Partial<Project['configuration']> = {}) =>
  ({
    id,
    source: 'user',
    status: 'configured',
    createdAt: updatedAt,
    updatedAt,
    configuration: validConfiguration({ name, ...overrides }),
  }) satisfies Project;

const projects = [
  makeProject('a', 'Beta', '2026-10-02T00:00:00.000Z'),
  makeProject('b', 'Alpha', '2026-10-03T00:00:00.000Z', {
    platform: 'mobile',
    stack: { mode: 'custom', technologies: ['flutter'] },
  }),
];

describe('filter-projects', () => {
  it('matches technology names in search and sorts by recency or name', () => {
    expect(filterProjects(projects, { ...DEFAULT_FILTERS, query: 'flutter' }).map((p) => p.id)).toEqual(['b']);
    expect(filterProjects(projects, DEFAULT_FILTERS).map((p) => p.id)).toEqual(['b', 'a']);
    expect(filterProjects(projects, { ...DEFAULT_FILTERS, sort: 'name' }).map((p) => p.id)).toEqual(['b', 'a']);
    expect(filterProjects(projects, { ...DEFAULT_FILTERS, platform: 'website' }).map((p) => p.id)).toEqual(['a']);
  });

  it('narrows untrusted values instead of casting them', () => {
    expect(parsePlatformFilter('mobile')).toBe('mobile');
    expect(parsePlatformFilter('tv')).toBe('all');
    expect(parsePlatformFilter(null)).toBe('all');
  });

  it('round-trips through URL parameters, omitting defaults', () => {
    const filters = { query: 'shop', platform: 'mobile', status: 'configured', sort: 'name' } as const;
    const params = filtersToSearchParams(filters);
    expect(filtersFromSearchParams(params)).toEqual(filters);
    expect(filtersToSearchParams(DEFAULT_FILTERS).toString()).toBe('');
  });
});
