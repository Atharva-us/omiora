import type { Project, ProjectConfiguration, ProjectHistoryEntry, ProjectNote } from '@/domain/projects/project';

export interface ProjectUpdate {
  name?: string;
  configuration?: ProjectConfiguration;
}

/**
 * Integration boundary for project persistence.
 *
 * Every implementation must:
 * - validate input with `domain/projects/rules.ts` and reject invalid data
 *   with `AppError('validation')`, regardless of what the UI checked;
 * - reject writes to sample projects with `AppError('read-only')`;
 * - reject unknown ids on writes with `AppError('not-found')`;
 * - surface persistence failures (`AppError('storage-unavailable' | 'network')`)
 *   instead of reporting success;
 * - return only data that passed schema validation.
 *
 * The executable form of this contract is
 * `src/test/contracts/project-service.contract.ts`.
 */
export interface ProjectService {
  /** Projects created by the current user, most recently updated first. Never includes samples. */
  listProjects(): Promise<Project[]>;
  /** Illustrative fixtures, marked `source: 'sample'`. */
  listSampleProjects(): Promise<Project[]>;
  /** `null` when no project (user or sample) has this id. */
  getProject(id: string): Promise<Project | null>;
  /** Saves a configuration. Never starts generation. */
  createProject(configuration: ProjectConfiguration): Promise<Project>;
  updateProject(id: string, update: ProjectUpdate): Promise<Project>;
  deleteProject(id: string): Promise<void>;
  /** Newest first. Empty for samples and for unknown ids. */
  getHistory(id: string): Promise<ProjectHistoryEntry[]>;
  /** Oldest first. Empty for samples and for unknown ids. */
  listNotes(id: string): Promise<ProjectNote[]>;
  addNote(id: string, content: string): Promise<ProjectNote>;
}
