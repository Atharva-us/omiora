import type { ProjectStatus } from './project';

/**
 * Allowed project status transitions. Only `draft → configured` happens
 * today; the remaining edges describe the engine workflow the backend will
 * own (see docs/ARCHITECTURE.md, "Agent system foundations"). The frontend
 * never advances a project past `configured` on its own.
 */
const TRANSITIONS: Record<ProjectStatus, readonly ProjectStatus[]> = {
  draft: ['configured'],
  configured: ['configured', 'queued'],
  queued: ['planning', 'failed', 'configured'],
  planning: ['generating', 'failed', 'configured'],
  generating: ['testing', 'failed', 'configured'],
  testing: ['ready', 'repairing', 'failed'],
  repairing: ['testing', 'failed'],
  ready: ['configured', 'queued'],
  failed: ['configured', 'queued'],
};

export function canTransition(from: ProjectStatus, to: ProjectStatus): boolean {
  return TRANSITIONS[from].includes(to);
}
