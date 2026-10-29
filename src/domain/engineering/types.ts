/**
 * Types describing the future AI engineering workflow. Nothing in the
 * frontend produces these values from a live engine; they define the
 * contract the workspace UI will render once the backend exists.
 */

/** The ten planned agents, in their intended implementation order. None is implemented yet. */
export const AGENT_ROLES = [
  'project-manager',
  'requirements-analyst',
  'reference-design',
  'software-architect',
  'frontend-engineer',
  'backend-engineer',
  'mobile-engineer',
  'database-engineer',
  'qa-debugging',
  'security-release',
] as const;

export type AgentRole = (typeof AGENT_ROLES)[number];

export type TaskStatus = 'pending' | 'in-progress' | 'blocked' | 'done' | 'failed';

export interface EngineeringTask {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  agent: AgentRole | null;
}

export interface AgentActivity {
  id: string;
  agent: AgentRole;
  message: string;
  at: string;
}

export type TestOutcome = 'passed' | 'failed' | 'skipped';

export interface TestResult {
  id: string;
  name: string;
  suite: string;
  outcome: TestOutcome;
  durationMs: number;
  message?: string;
}

export type BuildState = 'not-started' | 'queued' | 'running' | 'succeeded' | 'failed';

export type BuildLogLevel = 'info' | 'warn' | 'error';

export interface BuildLogEntry {
  id: string;
  at: string;
  level: BuildLogLevel;
  source: 'build' | 'test' | 'sandbox' | 'system';
  message: string;
}

export interface FileNode {
  path: string;
  name: string;
  kind: 'file' | 'directory';
  children?: FileNode[];
}
