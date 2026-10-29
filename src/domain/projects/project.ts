import { z } from 'zod/mini';

/**
 * Project domain model.
 *
 * Each type is inferred from its schema, so the runtime validator and the
 * static type cannot drift apart. The schemas validate *shape* (used for
 * persisted data and, later, API responses). Business rules such as length
 * limits and stack compatibility live in `rules.ts`.
 */

export const PLATFORM_TARGETS = ['website', 'mobile', 'both'] as const;
export const platformTargetSchema = z.enum(PLATFORM_TARGETS);
export type PlatformTarget = z.infer<typeof platformTargetSchema>;

export const TECHNOLOGY_IDS = ['react', 'nextjs', 'flutter', 'react-native', 'fastapi', 'nodejs', 'postgresql'] as const;
export const technologyIdSchema = z.enum(TECHNOLOGY_IDS);
export type TechnologyId = z.infer<typeof technologyIdSchema>;

export const REQUIREMENT_IDS = [
  'authentication',
  'database',
  'admin-dashboard',
  'payments',
  'notifications',
  'automated-tests',
] as const;
export const requirementIdSchema = z.enum(REQUIREMENT_IDS);
export type RequirementId = z.infer<typeof requirementIdSchema>;

/** "Recommend" carries no technologies: the planning service decides later. */
export const stackPreferenceSchema = z.discriminatedUnion('mode', [
  z.object({ mode: z.literal('recommend') }),
  z.object({ mode: z.literal('custom'), technologies: z.array(technologyIdSchema) }),
]);
export type StackPreference = z.infer<typeof stackPreferenceSchema>;
export type StackMode = StackPreference['mode'];

export const projectRequirementsSchema = z.object({
  features: z.array(requirementIdSchema),
  custom: z.string(),
});

/** Everything the user decides about a project. The single source of truth for its name and scope. */
export const projectConfigurationSchema = z.object({
  name: z.string(),
  description: z.string(),
  platform: platformTargetSchema,
  /** Empty string when no reference was given. */
  referenceUrl: z.string(),
  stack: stackPreferenceSchema,
  requirements: projectRequirementsSchema,
});
export type ProjectConfiguration = z.infer<typeof projectConfigurationSchema>;

export const PROJECT_STATUSES = [
  'draft',
  'configured',
  'queued',
  'planning',
  'generating',
  'testing',
  'repairing',
  'ready',
  'failed',
] as const;
export const projectStatusSchema = z.enum(PROJECT_STATUSES);
export type ProjectStatus = z.infer<typeof projectStatusSchema>;

/** `sample` projects are illustrative fixtures, never user data. */
export const projectSourceSchema = z.enum(['user', 'sample']);

const timestampSchema = z.iso.datetime();

/**
 * Identifiers are opaque strings assigned by the service implementation,
 * never by UI code. The demo adapter generates them locally; the API
 * adapter will use server-assigned ids.
 */
export const projectIdSchema = z.string().check(z.minLength(1));

export const projectSchema = z.object({
  id: projectIdSchema,
  source: projectSourceSchema,
  status: projectStatusSchema,
  configuration: projectConfigurationSchema,
  createdAt: timestampSchema,
  updatedAt: timestampSchema,
});
export type Project = z.infer<typeof projectSchema>;

export const projectHistoryEntrySchema = z.object({
  id: z.string().check(z.minLength(1)),
  projectId: projectIdSchema,
  at: timestampSchema,
  summary: z.string(),
});
export type ProjectHistoryEntry = z.infer<typeof projectHistoryEntrySchema>;

/** A requirement note the user adds from the workspace. Not a chat message: there is no assistant. */
export const projectNoteSchema = z.object({
  id: z.string().check(z.minLength(1)),
  content: z.string(),
  at: timestampSchema,
});
export type ProjectNote = z.infer<typeof projectNoteSchema>;

export function projectTechnologies(project: Pick<Project, 'configuration'>): TechnologyId[] {
  const { stack } = project.configuration;
  return stack.mode === 'custom' ? stack.technologies : [];
}
