import { describe, expect, it } from 'vitest';
import { AppError } from '@/domain/errors';
import { projectSchema } from '@/domain/projects/project';
import { PROJECT_LIMITS } from '@/domain/projects/rules';
import type { ProjectService } from '@/services/contracts/project-service';
import { validConfiguration } from '../fixtures';

/**
 * Executable specification for every ProjectService implementation. Run it
 * against the demo adapter today and against the HTTP adapter when it exists:
 *
 *   describeProjectServiceContract('http', () => createHttpProjectService(...));
 *
 * `setup` must return (or resolve to) a service with no user projects and at least one sample.
 */
export function describeProjectServiceContract(name: string, setup: () => ProjectService | Promise<ProjectService>) {
  describe(`ProjectService contract: ${name}`, () => {
    const expectAppError = async (promise: Promise<unknown>, code: AppError['code']) => {
      const error = await promise.then(
        () => null,
        (caught: unknown) => caught,
      );
      expect(error).toBeInstanceOf(AppError);
      expect((error as AppError).code).toBe(code);
      return error as AppError;
    };

    it('creates schema-valid, configured user projects without starting generation', async () => {
      const service = await setup();
      const project = await service.createProject(validConfiguration());
      expect(projectSchema.safeParse(project).success).toBe(true);
      expect(project).toMatchObject({ source: 'user', status: 'configured' });
      expect(await service.getProject(project.id)).toEqual(project);
    });

    it('normalises input before saving', async () => {
      const service = await setup();
      const project = await service.createProject(
        validConfiguration({
          name: '  Spaced  ',
          stack: { mode: 'custom', technologies: ['react', 'react'] },
          requirements: { features: ['payments', 'payments'], custom: '  note  ' },
        }),
      );
      expect(project.configuration.name).toBe('Spaced');
      expect(project.configuration.stack).toEqual({ mode: 'custom', technologies: ['react'] });
      expect(project.configuration.requirements).toEqual({ features: ['payments'], custom: 'note' });
    });

    it('enforces domain rules regardless of the caller', async () => {
      const service = await setup();
      const error = await expectAppError(
        service.createProject(validConfiguration({ stack: { mode: 'custom', technologies: ['react', 'nextjs'] } })),
        'validation',
      );
      expect(error.details.join(' ')).toMatch(/React and Next.js/);
      await expectAppError(service.createProject(validConfiguration({ name: '' })), 'validation');
      await expectAppError(service.createProject(validConfiguration({ referenceUrl: 'javascript:alert(1)' })), 'validation');

      const project = await service.createProject(validConfiguration());
      await expectAppError(service.updateProject(project.id, { name: 'x'.repeat(PROJECT_LIMITS.nameMax + 1) }), 'validation');
      await expectAppError(service.addNote(project.id, 'y'.repeat(PROJECT_LIMITS.noteMax + 1)), 'validation');
      await expectAppError(service.addNote(project.id, '   '), 'validation');
    });

    it('lists user projects newest first and never includes samples', async () => {
      const service = await setup();
      expect(await service.listProjects()).toEqual([]);
      const first = await service.createProject(validConfiguration({ name: 'First' }));
      await new Promise((resolve) => setTimeout(resolve, 5));
      const second = await service.createProject(validConfiguration({ name: 'Second' }));
      const listed = await service.listProjects();
      expect(listed.map((project) => project.id)).toEqual([second.id, first.id]);
      expect(listed.every((project) => project.source === 'user')).toBe(true);
    });

    it('serves samples read-only', async () => {
      const service = await setup();
      const [sample] = await service.listSampleProjects();
      expect(sample?.source).toBe('sample');
      if (!sample) return;
      expect(await service.getProject(sample.id)).toEqual(sample);
      await expectAppError(service.updateProject(sample.id, { name: 'Changed' }), 'read-only');
      await expectAppError(service.addNote(sample.id, 'note'), 'read-only');
      await expectAppError(service.deleteProject(sample.id), 'read-only');
      expect(await service.getHistory(sample.id)).toEqual([]);
    });

    it('distinguishes missing projects on reads and writes', async () => {
      const service = await setup();
      expect(await service.getProject('missing')).toBeNull();
      await expectAppError(service.updateProject('missing', { name: 'X' }), 'not-found');
      await expectAppError(service.deleteProject('missing'), 'not-found');
      await expectAppError(service.addNote('missing', 'note'), 'not-found');
    });

    it('updates name and configuration together and records history newest first', async () => {
      const service = await setup();
      const project = await service.createProject(validConfiguration());
      const renamed = await service.updateProject(project.id, { name: 'Renamed' });
      expect(renamed.configuration.name).toBe('Renamed');
      const reconfigured = await service.updateProject(project.id, {
        configuration: validConfiguration({ name: 'Renamed', platform: 'mobile' }),
      });
      expect(reconfigured.configuration.platform).toBe('mobile');
      const history = await service.getHistory(project.id);
      expect(history.map((entry) => entry.summary)).toEqual([
        'Configuration updated.',
        'Renamed to "Renamed".',
        'Project created from the configuration wizard.',
      ]);
    });

    it('keeps notes oldest first and deletes everything with the project', async () => {
      const service = await setup();
      const project = await service.createProject(validConfiguration());
      await service.addNote(project.id, 'First note');
      await service.addNote(project.id, 'Second note');
      expect((await service.listNotes(project.id)).map((note) => note.content)).toEqual(['First note', 'Second note']);
      await service.deleteProject(project.id);
      expect(await service.getProject(project.id)).toBeNull();
      expect(await service.listNotes(project.id)).toEqual([]);
      expect(await service.getHistory(project.id)).toEqual([]);
    });
  });
}
