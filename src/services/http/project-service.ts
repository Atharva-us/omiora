import { z } from 'zod/mini';
import { isAppError } from '@/domain/errors';
import {
  projectHistoryEntrySchema,
  projectNoteSchema,
  projectSchema,
  type ProjectConfiguration,
} from '@/domain/projects/project';
import type { ProjectService, ProjectUpdate } from '../contracts/project-service';
import type { HttpClient } from './http-client';

const pageSchema = z.object({ items: z.array(projectSchema), nextCursor: z.nullable(z.string()) });
const PAGE_SIZE = 100;

const path = (id: string) => `/api/v1/projects/${encodeURIComponent(id)}`;

/** The API answers 404 for a missing project's sub-resources; the ProjectService contract reads that as "none". */
async function emptyIfNotFound<T>(request: Promise<T[]>): Promise<T[]> {
  try {
    return await request;
  } catch (error) {
    if (isAppError(error) && error.code === 'not-found') return [];
    throw error;
  }
}

/** ProjectService over the FastAPI backend (docs/BACKEND_CONTRACTS.md §2). */
export function createHttpProjectService(http: HttpClient): ProjectService {
  return {
    async listProjects() {
      const projects = [];
      let cursor: string | null = null;
      do {
        const query: string = `?limit=${PAGE_SIZE}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
        const page: z.infer<typeof pageSchema> = await http.request('GET', `/api/v1/projects${query}`, { schema: pageSchema });
        projects.push(...page.items);
        cursor = page.nextCursor;
      } while (cursor);
      return projects;
    },
    listSampleProjects: () => http.request('GET', '/api/v1/projects/samples', { schema: z.array(projectSchema) }),
    async getProject(id) {
      try {
        return await http.request('GET', path(id), { schema: projectSchema });
      } catch (error) {
        if (isAppError(error) && error.code === 'not-found') return null;
        throw error;
      }
    },
    createProject: (configuration: ProjectConfiguration) =>
      http.request('POST', '/api/v1/projects', { body: configuration, schema: projectSchema }),
    updateProject: (id, update: ProjectUpdate) => http.request('PATCH', path(id), { body: update, schema: projectSchema }),
    deleteProject: (id) => http.request('DELETE', path(id)),
    getHistory: (id) =>
      emptyIfNotFound(http.request('GET', `${path(id)}/history`, { schema: z.array(projectHistoryEntrySchema) })),
    listNotes: (id) => emptyIfNotFound(http.request('GET', `${path(id)}/notes`, { schema: z.array(projectNoteSchema) })),
    addNote: (id, content) => http.request('POST', `${path(id)}/notes`, { body: { content }, schema: projectNoteSchema }),
  };
}
