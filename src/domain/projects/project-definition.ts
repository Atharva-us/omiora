import type { Project } from './project';

export const PROJECT_DEFINITION_FILENAME = 'omniora.project.json';

/**
 * The portable, versionable description of a project, derived from the
 * saved configuration. It is the only "file" a project has until code
 * generation exists.
 */
export function toProjectDefinition(project: Project) {
  const { configuration } = project;
  return {
    schemaVersion: 1,
    name: configuration.name,
    description: configuration.description,
    platform: configuration.platform,
    referenceUrl: configuration.referenceUrl || null,
    stack: configuration.stack,
    requirements: configuration.requirements,
  };
}

export function projectDefinitionJson(project: Project): string {
  return `${JSON.stringify(toProjectDefinition(project), null, 2)}\n`;
}
