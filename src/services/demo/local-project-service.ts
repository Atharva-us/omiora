import { z } from 'zod/mini';
import { AppError } from '@/domain/errors';
import {
  projectHistoryEntrySchema,
  projectNoteSchema,
  projectSchema,
  type Project,
  type ProjectConfiguration,
  type ProjectHistoryEntry,
  type ProjectNote,
} from '@/domain/projects/project';
import {
  blockingMessages,
  hasBlockingIssues,
  normalizeConfiguration,
  validateNoteContent,
  validateProjectConfiguration,
  validateProjectName,
} from '@/domain/projects/rules';
import type { KeyValueStore } from '@/infrastructure/storage/key-value-store';
import type { Logger } from '@/infrastructure/telemetry/logger';
import type { ProjectService, ProjectUpdate } from '../contracts/project-service';
import { createDemoId } from './ids';
import { SAMPLE_PROJECTS } from './sample-projects';

/**
 * DEMO ADAPTER: persists projects in a KeyValueStore (localStorage in the
 * browser) so the frontend is fully interactive without a backend. Data
 * stays on this device. Everything read back is treated as untrusted and
 * validated record by record.
 */

export const DEMO_STORE_KEY = 'omniora.demo.v1';

interface DemoStore {
  projects: Project[];
  history: ProjectHistoryEntry[];
  notes: Record<string, ProjectNote[]>;
}

/** Keeps valid records and counts the rest, so one corrupted entry cannot take down the whole store. */
function parseEach<T>(schema: z.ZodMiniType<T>, values: unknown): { valid: T[]; invalid: number } {
  if (!Array.isArray(values)) return { valid: [], invalid: values === undefined ? 0 : 1 };
  const valid: T[] = [];
  let invalid = 0;
  for (const value of values) {
    const result = schema.safeParse(value);
    if (result.success) valid.push(result.data);
    else invalid += 1;
  }
  return { valid, invalid };
}

const rawStoreSchema = z.object({
  projects: z.unknown(),
  history: z.unknown(),
  notes: z.catch(z.record(z.string(), z.unknown()), {}),
});

/**
 * Sorts by timestamp descending. Stored arrays are append-only, so ties
 * (several events in the same millisecond) fall back to reverse insertion
 * order: the later write is newer.
 */
function newestFirst<T>(items: readonly T[], timestamp: (item: T) => string): T[] {
  return [...items].reverse().sort((a, b) => timestamp(b).localeCompare(timestamp(a)));
}

// Samples are served from fixtures, never from storage; a stored "sample" is invalid.
const userProjectSchema = projectSchema.check(z.refine((project) => project.source === 'user'));

export interface LocalProjectServiceOptions {
  store: KeyValueStore;
  logger: Logger;
  now?: () => Date;
}

export function createLocalProjectService({ store, logger, now = () => new Date() }: LocalProjectServiceOptions): ProjectService {
  const timestamp = () => now().toISOString();

  const load = (): DemoStore => {
    const raw = store.get(DEMO_STORE_KEY);
    if (raw === undefined) return { projects: [], history: [], notes: {} };
    const parsedRoot = rawStoreSchema.safeParse(raw);
    if (!parsedRoot.success) {
      logger.warn('demo-store.discarded', { reason: 'unrecognised root shape' });
      return { projects: [], history: [], notes: {} };
    }
    const projects = parseEach(userProjectSchema, parsedRoot.data.projects);
    const history = parseEach(projectHistoryEntrySchema, parsedRoot.data.history);
    let invalidNotes = 0;
    const notes: DemoStore['notes'] = {};
    for (const [projectId, entries] of Object.entries(parsedRoot.data.notes)) {
      const parsed = parseEach(projectNoteSchema, entries);
      notes[projectId] = parsed.valid;
      invalidNotes += parsed.invalid;
    }
    const invalid = { projects: projects.invalid, history: history.invalid, notes: invalidNotes };
    if (invalid.projects + invalid.history + invalid.notes > 0) logger.warn('demo-store.invalid-records-dropped', invalid);
    return { projects: projects.valid, history: history.valid, notes };
  };

  // Throws AppError('storage-unavailable') if the write fails; callers must not report success.
  const save = (data: DemoStore) => store.set(DEMO_STORE_KEY, data);

  const record = (data: DemoStore, projectId: string, summary: string, at: string) => {
    data.history.push({ id: createDemoId('evt'), projectId, at, summary });
  };

  const findSample = (id: string) => SAMPLE_PROJECTS.find((project) => project.id === id) ?? null;

  const requireUserProject = (data: DemoStore, id: string): Project => {
    if (findSample(id)) throw new AppError('read-only', 'Sample projects are read-only.');
    const project = data.projects.find((candidate) => candidate.id === id);
    if (!project) throw new AppError('not-found', 'This project no longer exists.');
    return project;
  };

  const validated = (configuration: ProjectConfiguration): ProjectConfiguration => {
    const normalized = normalizeConfiguration(configuration);
    const issues = validateProjectConfiguration(normalized);
    if (hasBlockingIssues(issues)) {
      throw new AppError('validation', 'The project configuration is not valid.', { details: blockingMessages(issues) });
    }
    return normalized;
  };

  return {
    async listProjects() {
      return newestFirst(load().projects, (project) => project.updatedAt);
    },

    async listSampleProjects() {
      return [...SAMPLE_PROJECTS];
    },

    async getProject(id) {
      return findSample(id) ?? load().projects.find((project) => project.id === id) ?? null;
    },

    async createProject(configuration) {
      const valid = validated(configuration);
      const data = load();
      const at = timestamp();
      const project: Project = {
        id: createDemoId('prj'),
        source: 'user',
        status: 'configured',
        configuration: valid,
        createdAt: at,
        updatedAt: at,
      };
      data.projects.push(project);
      record(data, project.id, 'Project created from the configuration wizard.', at);
      save(data);
      return project;
    },

    async updateProject(id, update: ProjectUpdate) {
      const data = load();
      const project = requireUserProject(data, id);
      const at = timestamp();
      const changes: string[] = [];
      let configuration = project.configuration;

      if (update.configuration) {
        configuration = validated(update.configuration);
        changes.push('Configuration updated.');
      }
      if (update.name !== undefined) {
        const problem = validateProjectName(update.name);
        if (problem) throw new AppError('validation', 'The project name is not valid.', { details: [problem] });
        const name = update.name.trim();
        if (name !== project.configuration.name) changes.push(`Renamed to "${name}".`);
        configuration = { ...configuration, name };
      }
      if (changes.length === 0) return project;

      const updated: Project = { ...project, configuration, updatedAt: at };
      data.projects = data.projects.map((candidate) => (candidate.id === id ? updated : candidate));
      changes.forEach((summary) => record(data, id, summary, at));
      save(data);
      return updated;
    },

    async deleteProject(id) {
      const data = load();
      requireUserProject(data, id);
      data.projects = data.projects.filter((project) => project.id !== id);
      data.history = data.history.filter((entry) => entry.projectId !== id);
      delete data.notes[id];
      save(data);
    },

    async getHistory(id) {
      if (findSample(id)) return [];
      return newestFirst(
        load().history.filter((entry) => entry.projectId === id),
        (entry) => entry.at,
      );
    },

    async listNotes(id) {
      return load().notes[id] ?? [];
    },

    async addNote(id, content) {
      const problem = validateNoteContent(content);
      if (problem) throw new AppError('validation', 'The note was not saved.', { details: [problem] });
      const data = load();
      const project = requireUserProject(data, id);
      const at = timestamp();
      const note: ProjectNote = { id: createDemoId('note'), content: content.trim(), at };
      data.notes[id] = [...(data.notes[id] ?? []), note];
      data.projects = data.projects.map((candidate) => (candidate.id === project.id ? { ...candidate, updatedAt: at } : candidate));
      record(data, id, 'Requirement note added.', at);
      save(data);
      return note;
    },
  };
}
