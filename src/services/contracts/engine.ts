/**
 * FUTURE AI ENGINE CONTRACTS — interfaces only.
 *
 * None of these services are implemented in Phase 1, and no fake or
 * simulated implementations exist. Each interface describes what the
 * frontend will call once the FastAPI backend and isolated execution
 * infrastructure are built. See docs/BACKEND_CONTRACTS.md.
 *
 * Security invariant: generated or user-supplied code is NEVER executed on
 * the application server. Execution happens only inside isolated,
 * resource-limited sandboxes with restricted filesystem and network access.
 */
import type {
  AgentActivity,
  AgentRole,
  BuildLogEntry,
  BuildState,
  EngineeringTask,
  FileNode,
  TestResult,
} from '@/domain/engineering/types';
import type { ProjectConfiguration, TechnologyId } from '@/domain/projects/project';

export type Unsubscribe = () => void;

// ---------------------------------------------------------------------------
// Planning and analysis
// ---------------------------------------------------------------------------

export interface ProjectPlan {
  projectId: string;
  summary: string;
  recommendedStack: TechnologyId[];
  tasks: EngineeringTask[];
  openQuestions: string[];
}

export interface ProjectPlanningService {
  createPlan(projectId: string, configuration: ProjectConfiguration): Promise<ProjectPlan>;
  revisePlan(projectId: string, feedback: string): Promise<ProjectPlan>;
}

export interface AnalysedRequirement {
  id: string;
  statement: string;
  kind: 'functional' | 'non-functional' | 'constraint';
  priority: 'must' | 'should' | 'could';
  ambiguity: string | null;
}

export interface RequirementsAnalysisService {
  analyse(configuration: ProjectConfiguration): Promise<AnalysedRequirement[]>;
}

export interface ReferenceAnalysis {
  url: string;
  palette: string[];
  typography: string[];
  layoutPatterns: string[];
  components: string[];
  /** Analysis extracts design language only; assets are never copied. */
  notes: string;
}

export interface ReferenceAnalysisService {
  analyseReference(url: string): Promise<ReferenceAnalysis>;
}

// ---------------------------------------------------------------------------
// Models and agents
// ---------------------------------------------------------------------------

export type ModelTask = 'planning' | 'code-generation' | 'code-review' | 'vision' | 'repair' | 'summarisation';

export interface ModelRoute {
  task: ModelTask;
  provider: string;
  model: string;
  maxOutputTokens: number;
}

export interface ModelRoutingService {
  resolve(task: ModelTask): Promise<ModelRoute>;
}

export interface AgentRun {
  id: string;
  projectId: string;
  state: 'queued' | 'running' | 'awaiting-approval' | 'completed' | 'failed' | 'cancelled';
  activeAgents: AgentRole[];
  startedAt: string | null;
}

export interface AgentOrchestrationService {
  start(projectId: string): Promise<AgentRun>;
  cancel(runId: string): Promise<void>;
  subscribe(runId: string, onActivity: (activity: AgentActivity) => void): Unsubscribe;
}

// ---------------------------------------------------------------------------
// Files, sandboxes, and automation
// ---------------------------------------------------------------------------

export interface FileOperationsService {
  listTree(projectId: string): Promise<FileNode>;
  readFile(projectId: string, path: string): Promise<string>;
  writeFile(projectId: string, path: string, contents: string): Promise<void>;
  deleteFile(projectId: string, path: string): Promise<void>;
}

export interface SandboxLimits {
  cpuCores: number;
  memoryMb: number;
  timeoutSeconds: number;
  /** Default deny. Only explicitly allowed hosts (e.g. package registries). */
  networkAllowList: string[];
}

export interface SandboxCommandResult {
  exitCode: number;
  stdout: string;
  stderr: string;
  durationMs: number;
  timedOut: boolean;
}

export interface SandboxExecutionService {
  run(projectId: string, command: string[], limits: SandboxLimits): Promise<SandboxCommandResult>;
}

export interface BrowserCheckResult {
  url: string;
  screenshotUrl: string | null;
  consoleErrors: string[];
  passed: boolean;
}

export interface BrowserAutomationService {
  check(projectId: string, path: string, viewport: { width: number; height: number }): Promise<BrowserCheckResult>;
}

// ---------------------------------------------------------------------------
// Build, test, repair, delivery
// ---------------------------------------------------------------------------

export interface BuildRun {
  id: string;
  projectId: string;
  state: BuildState;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface BuildExecutionService {
  startBuild(projectId: string): Promise<BuildRun>;
  getBuild(buildId: string): Promise<BuildRun>;
  streamLogs(buildId: string, onEntry: (entry: BuildLogEntry) => void): Unsubscribe;
}

export interface TestRun {
  id: string;
  projectId: string;
  state: BuildState;
  results: TestResult[];
}

export interface AutomatedTestingService {
  runTests(projectId: string): Promise<TestRun>;
  getTestRun(testRunId: string): Promise<TestRun>;
}

export interface RepairAttempt {
  id: string;
  testRunId: string;
  changedFiles: string[];
  rationale: string;
  outcome: 'pending' | 'fixed' | 'not-fixed';
}

export interface CodeRepairService {
  repair(projectId: string, testRunId: string): Promise<RepairAttempt>;
}

export interface PackageArtifact {
  projectId: string;
  downloadUrl: string;
  sizeBytes: number;
  sha256: string;
  expiresAt: string;
}

export interface PackagingService {
  createZip(projectId: string): Promise<PackageArtifact>;
}

export interface Deployment {
  id: string;
  projectId: string;
  target: 'preview' | 'production';
  state: 'pending' | 'building' | 'live' | 'failed';
  url: string | null;
}

export interface DeploymentService {
  deploy(projectId: string, target: Deployment['target']): Promise<Deployment>;
  getDeployment(deploymentId: string): Promise<Deployment>;
}
