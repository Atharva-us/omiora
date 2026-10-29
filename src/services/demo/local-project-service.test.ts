import { describe, expect, it } from 'vitest';
import { AppError } from '@/domain/errors';
import { createMemoryStore, type KeyValueStore } from '@/infrastructure/storage/key-value-store';
import { createMemoryLogger } from '@/infrastructure/telemetry/logger';
import { describeProjectServiceContract } from '@/test/contracts/project-service.contract';
import { validConfiguration } from '@/test/fixtures';
import { createLocalProjectService, DEMO_STORE_KEY } from './local-project-service';
import { SAMPLE_PROJECTS } from './sample-projects';

function setup(store: KeyValueStore = createMemoryStore()) {
  const logger = createMemoryLogger();
  return { service: createLocalProjectService({ store, logger }), logger, store };
}

describeProjectServiceContract('demo (local storage)', () => setup().service);

describe('createLocalProjectService (demo adapter specifics)', () => {
  it('serves every sample fixture, each marked as a sample', async () => {
    const samples = await setup().service.listSampleProjects();
    expect(samples).toHaveLength(SAMPLE_PROJECTS.length);
    expect(samples.every((project) => project.source === 'sample')).toBe(true);
  });

  it('persists across service instances sharing a store', async () => {
    const store = createMemoryStore();
    const project = await setup(store).service.createProject(validConfiguration());
    expect(await setup(store).service.getProject(project.id)).toEqual(project);
  });

  // Regression for audit R1: one corrupted record used to crash the dashboard.
  it('drops invalid persisted records individually and logs a warning', async () => {
    const { service, store } = setup();
    const good = await service.createProject(validConfiguration({ name: 'Good' }));
    const raw = store.get(DEMO_STORE_KEY) as { projects: unknown[] };
    store.set(DEMO_STORE_KEY, {
      ...raw,
      projects: [...raw.projects, { ...good, id: 'prj_bad', configuration: { ...good.configuration, platform: 'tv' } }],
    });

    const fresh = setup(store);
    const listed = await fresh.service.listProjects();
    expect(listed.map((project) => project.id)).toEqual([good.id]);
    expect(fresh.logger.entries).toContainEqual(
      expect.objectContaining({ level: 'warn', event: 'demo-store.invalid-records-dropped' }),
    );
  });

  it('ignores user-store entries that claim to be samples', async () => {
    const { service, store } = setup();
    const project = await service.createProject(validConfiguration());
    const raw = store.get(DEMO_STORE_KEY) as { projects: Record<string, unknown>[] };
    store.set(DEMO_STORE_KEY, { ...raw, projects: raw.projects.map((entry) => ({ ...entry, source: 'sample' })) });
    expect(await setup(store).service.getProject(project.id)).toBeNull();
  });

  it('reads Phase 1 records that still carry duplicated top-level fields', async () => {
    const legacyProject = {
      id: 'prj_legacy',
      name: 'Legacy',
      description: 'Stored before the domain refactor',
      platform: 'website',
      technologies: [],
      status: 'configured',
      source: 'user',
      createdAt: '2026-10-29T09:00:00.000Z',
      updatedAt: '2026-10-29T09:00:00.000Z',
      configuration: { ...validConfiguration({ name: 'Legacy' }), stack: { mode: 'recommend', technologies: [] } },
    };
    const store = createMemoryStore({ [DEMO_STORE_KEY]: { projects: [legacyProject], history: [], notes: {} } });
    const project = await setup(store).service.getProject('prj_legacy');
    expect(project?.configuration.name).toBe('Legacy');
    expect(project?.configuration.stack).toEqual({ mode: 'recommend' });
    expect(project).not.toHaveProperty('name');
  });

  // Regression for audit R2: a failed write used to report success and lose the project.
  it('propagates storage failures instead of reporting success', async () => {
    const failing: KeyValueStore = {
      ...createMemoryStore(),
      set: () => {
        throw new AppError('storage-unavailable', 'Storage is full.');
      },
    };
    const { service } = setup(failing);
    await expect(service.createProject(validConfiguration())).rejects.toMatchObject({ code: 'storage-unavailable' });
    expect(await service.listProjects()).toEqual([]);
  });

  // Regression: events in the same millisecond were returned oldest first, breaking the "newest first" contract.
  it('orders same-timestamp events and projects by write order', async () => {
    const frozen = new Date('2026-10-29T12:00:00.000Z');
    const service = createLocalProjectService({ store: createMemoryStore(), logger: createMemoryLogger(), now: () => frozen });
    const first = await service.createProject(validConfiguration({ name: 'First' }));
    const second = await service.createProject(validConfiguration({ name: 'Second' }));
    expect((await service.listProjects()).map((project) => project.id)).toEqual([second.id, first.id]);

    await service.updateProject(first.id, { name: 'Renamed', configuration: validConfiguration({ platform: 'mobile' }) });
    await service.addNote(first.id, 'Later note');
    expect((await service.getHistory(first.id)).map((entry) => entry.summary)).toEqual([
      'Requirement note added.',
      'Renamed to "Renamed".',
      'Configuration updated.',
      'Project created from the configuration wizard.',
    ]);
  });

  it('starts empty when the stored root is unrecognisable', async () => {
    const store = createMemoryStore({ [DEMO_STORE_KEY]: 'not an object' });
    const { service, logger } = setup(store);
    expect(await service.listProjects()).toEqual([]);
    expect(logger.entries[0]?.event).toBe('demo-store.discarded');
  });
});
