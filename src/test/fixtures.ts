import type { ProjectConfiguration } from '@/domain/projects/project';

/** A configuration that passes every domain rule; override fields per test. */
export function validConfiguration(overrides: Partial<ProjectConfiguration> = {}): ProjectConfiguration {
  return {
    name: 'Maker Market',
    description: 'A storefront for handmade goods',
    platform: 'website',
    referenceUrl: '',
    stack: { mode: 'recommend' },
    requirements: { features: [], custom: '' },
    ...overrides,
  };
}
