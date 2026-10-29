import type { ServiceMode } from './services-context';

/**
 * Single source of truth for what this build can actually do, per service
 * mode. The UI reads this to label features honestly; update it in the same
 * change that implements or removes a capability.
 */
export type CapabilityStatus = 'available' | 'demo' | 'not-connected';

export interface Capability {
  id: string;
  name: string;
  status: CapabilityStatus;
  detail: string;
}

const NOT_CONNECTED: readonly Capability[] = [
  {
    id: 'reference-analysis',
    name: 'Reference-to-design analysis',
    status: 'not-connected',
    detail: 'Contract defined (ReferenceAnalysisService). Reference URLs are stored with the configuration only.',
  },
  {
    id: 'agents-2-10',
    name: 'Agents 2–10 (design, architecture, engineering, QA, security)',
    status: 'not-connected',
    detail: 'Not implemented. The Project Manager may propose tasks for them; nothing executes those tasks.',
  },
  {
    id: 'sandbox',
    name: 'Sandboxed execution and browser automation',
    status: 'not-connected',
    detail: 'Not implemented. Requires isolated, resource-limited runners with default-deny networking.',
  },
  {
    id: 'build-test-repair',
    name: 'Code generation, build, test, and repair',
    status: 'not-connected',
    detail: 'Not implemented. Approving a plan records consent only; no code is written or run.',
  },
  {
    id: 'export',
    name: 'ZIP export',
    status: 'not-connected',
    detail: 'No generated source exists to package yet. The project configuration can be downloaded as JSON.',
  },
  {
    id: 'deployment',
    name: 'Deployment',
    status: 'not-connected',
    detail: 'Contract defined (DeploymentService).',
  },
];

export function capabilitiesFor(mode: ServiceMode): readonly Capability[] {
  if (mode === 'api') {
    return [
      {
        id: 'project-configuration',
        name: 'Projects and configuration',
        status: 'available',
        detail: 'Stored in PostgreSQL by the Omniora API, per account.',
      },
      {
        id: 'authentication',
        name: 'Accounts and authentication',
        status: 'available',
        detail: 'Email and password accounts with server-side sessions. Email verification and password reset are not available yet.',
      },
      {
        id: 'planning',
        name: 'Project Manager agent (planning)',
        status: 'available',
        detail:
          'Produces a validated plan for your approval when the server has a model provider configured. It never writes or runs code.',
      },
      ...NOT_CONNECTED,
    ];
  }
  return [
    {
      id: 'project-configuration',
      name: 'Project configuration',
      status: 'demo',
      detail: 'The wizard works end to end. Projects are saved in this browser only (demo storage adapter).',
    },
    {
      id: 'authentication',
      name: 'Accounts and authentication',
      status: 'not-connected',
      detail: 'Demo mode has no backend, so no account can sign in.',
    },
    {
      id: 'planning',
      name: 'Project Manager agent (planning)',
      status: 'not-connected',
      detail: 'Requires API mode and a running Omniora backend.',
    },
    ...NOT_CONNECTED,
  ];
}
