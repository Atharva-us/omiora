import { describe, expect, it } from 'vitest';
import { validConfiguration } from '@/test/fixtures';
import { canTransition } from './lifecycle';
import { projectConfigurationSchema, projectSchema, projectTechnologies } from './project';

const project = {
  id: 'prj_1',
  source: 'user',
  status: 'configured',
  configuration: validConfiguration(),
  createdAt: '2026-10-29T09:00:00.000Z',
  updatedAt: '2026-10-29T09:00:00.000Z',
};

describe('project schema', () => {
  it('accepts a valid project', () => {
    expect(projectSchema.parse(project)).toEqual(project);
  });

  it('rejects unknown enum values and malformed timestamps', () => {
    expect(projectSchema.safeParse({ ...project, status: 'deployed' }).success).toBe(false);
    expect(projectSchema.safeParse({ ...project, updatedAt: 'yesterday' }).success).toBe(false);
    expect(
      projectConfigurationSchema.safeParse({ ...validConfiguration(), stack: { mode: 'custom', technologies: ['cobol'] } })
        .success,
    ).toBe(false);
  });

  it('requires technologies only for custom stacks', () => {
    expect(projectConfigurationSchema.safeParse({ ...validConfiguration(), stack: { mode: 'custom' } }).success).toBe(false);
    expect(projectTechnologies({ configuration: validConfiguration() })).toEqual([]);
    expect(
      projectTechnologies({ configuration: validConfiguration({ stack: { mode: 'custom', technologies: ['nodejs'] } }) }),
    ).toEqual(['nodejs']);
  });
});

describe('project lifecycle', () => {
  it('allows the engine workflow and blocks skipping verification', () => {
    expect(canTransition('draft', 'configured')).toBe(true);
    expect(canTransition('configured', 'queued')).toBe(true);
    expect(canTransition('testing', 'ready')).toBe(true);
    expect(canTransition('generating', 'ready')).toBe(false);
    expect(canTransition('configured', 'ready')).toBe(false);
    expect(canTransition('repairing', 'ready')).toBe(false);
  });
});
