import type { ProjectConfiguration } from './project';
import { validateStack } from './stack-validation';

/**
 * Business rules for projects. Enforced by every ProjectService
 * implementation and reused by the UI for immediate feedback, so the two
 * can never disagree. A future backend must enforce the same limits.
 */
export const PROJECT_LIMITS = {
  nameMax: 80,
  descriptionMin: 10,
  descriptionMax: 2000,
  customRequirementsMax: 1000,
  noteMax: 1000,
} as const;

export type ConfigurationField = 'name' | 'description' | 'referenceUrl' | 'custom';

export interface ConfigurationIssues {
  fields: Partial<Record<ConfigurationField, string>>;
  stackErrors: string[];
  stackWarnings: string[];
}

export function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    // The URL constructor throws for anything unparseable; that simply means "not a URL".
    return false;
  }
}

export function validateProjectName(name: string): string | undefined {
  const trimmed = name.trim();
  if (!trimmed) return 'Give your project a name.';
  if (trimmed.length > PROJECT_LIMITS.nameMax) return `Use ${PROJECT_LIMITS.nameMax} characters or fewer.`;
  return undefined;
}

export function validateProjectDescription(description: string): string | undefined {
  const trimmed = description.trim();
  if (!trimmed) return 'Describe what you want to build.';
  if (trimmed.length < PROJECT_LIMITS.descriptionMin)
    return `Add a little more detail (at least ${PROJECT_LIMITS.descriptionMin} characters).`;
  if (trimmed.length > PROJECT_LIMITS.descriptionMax) return `Use ${PROJECT_LIMITS.descriptionMax} characters or fewer.`;
  return undefined;
}

export function validateReferenceUrl(url: string): string | undefined {
  const trimmed = url.trim();
  if (trimmed && !isHttpUrl(trimmed)) return 'Enter a full URL starting with http:// or https://.';
  return undefined;
}

export function validateCustomRequirements(custom: string): string | undefined {
  if (custom.trim().length > PROJECT_LIMITS.customRequirementsMax)
    return `Use ${PROJECT_LIMITS.customRequirementsMax} characters or fewer.`;
  return undefined;
}

export function validateNoteContent(content: string): string | undefined {
  const trimmed = content.trim();
  if (!trimmed) return 'Write a note before adding it.';
  if (trimmed.length > PROJECT_LIMITS.noteMax) return `Keep notes under ${PROJECT_LIMITS.noteMax} characters.`;
  return undefined;
}

export function validateProjectConfiguration(configuration: ProjectConfiguration): ConfigurationIssues {
  const fields: ConfigurationIssues['fields'] = {};
  const checks: [ConfigurationField, string | undefined][] = [
    ['name', validateProjectName(configuration.name)],
    ['description', validateProjectDescription(configuration.description)],
    ['referenceUrl', validateReferenceUrl(configuration.referenceUrl)],
    ['custom', validateCustomRequirements(configuration.requirements.custom)],
  ];
  for (const [field, message] of checks) if (message) fields[field] = message;
  const stack = validateStack(configuration.platform, configuration.stack);
  return { fields, stackErrors: stack.errors, stackWarnings: stack.warnings };
}

export function hasBlockingIssues(issues: ConfigurationIssues): boolean {
  return Object.keys(issues.fields).length > 0 || issues.stackErrors.length > 0;
}

/** All blocking messages, flattened, for error details. */
export function blockingMessages(issues: ConfigurationIssues): string[] {
  return [...Object.values(issues.fields), ...issues.stackErrors];
}

/** Trims free-text fields and removes duplicate selections before saving. */
export function normalizeConfiguration(configuration: ProjectConfiguration): ProjectConfiguration {
  const { stack, requirements } = configuration;
  return {
    name: configuration.name.trim(),
    description: configuration.description.trim(),
    platform: configuration.platform,
    referenceUrl: configuration.referenceUrl.trim(),
    stack: stack.mode === 'custom' ? { mode: 'custom', technologies: [...new Set(stack.technologies)] } : { mode: 'recommend' },
    requirements: { features: [...new Set(requirements.features)], custom: requirements.custom.trim() },
  };
}
