import { screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AppError } from '@/domain/errors';
import type { Approval, Run, RunDetail, RunEvent } from '@/domain/runs/run';
import type { RunService, RunStreamHandlers } from '@/services/contracts/run-service';
import { validConfiguration } from '@/test/fixtures';
import { createTestServices, renderApp } from '@/test/render-app';

const at = '2026-10-29T12:00:00.000Z';

function runRecord(overrides: Partial<Run> = {}): Run {
  return {
    id: 'run-1', projectId: 'p', agentRole: 'project-manager', state: 'awaiting-approval', currentPlanVersion: 1,
    failureCode: null, failureMessage: null, lastEventSeq: 7, createdAt: at, updatedAt: at, ...overrides,
  };
}

function awaitingDetail(): RunDetail {
  return {
    run: runRecord(),
    plan: {
      version: 1,
      createdAt: at,
      content: {
        summary: 'A storefront for makers with hosted checkout.',
        requirements: [
          { id: 'R1', statement: 'Shoppers can browse products.', kind: 'functional', priority: 'must', source: 'user' },
        ],
        assumptions: ['Single currency at launch.'],
        openQuestions: [{ id: 'Q1', question: 'Which payment provider?', whyItMatters: 'Affects checkout.', blocking: true }],
        recommendedStack: { technologies: ['nextjs', 'postgresql'], rationale: 'SEO and relational data.' },
        requiredApprovals: [{ gate: 'plan', description: 'Approve scope.' }],
      },
    },
    tasks: [
      { key: 'T1', title: 'Data model', description: 'Schema.', acceptanceCriteria: ['Reviewed'], dependsOn: [],
        requirementIds: ['R1'], suggestedAgent: 'database-engineer', status: 'proposed' },
      { key: 'T2', title: 'Catalogue', description: 'Pages.', acceptanceCriteria: ['Renders'], dependsOn: ['T1'],
        requirementIds: ['R1'], suggestedAgent: 'frontend-engineer', status: 'proposed' },
    ],
    approvals: [{ id: 'ap-1', planVersion: 1, gate: 'plan', status: 'pending', comment: null, decidedAt: null, createdAt: at }],
    attempts: [],
  };
}

function fakeRuns(initial: RunDetail | null) {
  let detail = initial;
  let handlers: RunStreamHandlers | null = null;
  const service: RunService & { emit: (event: RunEvent) => void } = {
    available: true,
    listRuns: vi.fn(async () => (detail ? [detail.run] : [])),
    getRun: vi.fn(async () => {
      if (!detail) throw new AppError('not-found', 'No run.');
      return detail;
    }),
    startPlanning: vi.fn(async () => {
      detail = { run: runRecord({ state: 'queued', currentPlanVersion: null }), plan: null, tasks: [], approvals: [], attempts: [] };
      return detail.run;
    }),
    cancel: vi.fn(async () => runRecord({ state: 'cancelled' })),
    decide: vi.fn(async (_runId, _approvalId, input) => {
      if (!detail) throw new Error('no run');
      const status = input.decision === 'approve' ? 'approved' : input.decision === 'reject' ? 'rejected' : 'revision-requested';
      const approval: Approval = { ...detail.approvals[0]!, status, decidedAt: at };
      detail = { ...detail, run: { ...detail.run, state: input.decision === 'revise' ? 'queued' : status === 'approved' ? 'approved' : 'rejected' }, approvals: [approval] };
      return approval;
    }),
    listEvents: vi.fn(async () => []),
    subscribe: vi.fn((_runId, _after, h: RunStreamHandlers) => {
      handlers = h;
      return () => {
        handlers = null;
      };
    }),
    emit: (event) => handlers?.onEvent(event),
  };
  return service;
}

async function openPlan(runs: RunService | null) {
  const base = createTestServices();
  const services = runs ? { ...base, runs } : base;
  const project = await services.projects.createProject(validConfiguration({ name: 'Maker Market' }));
  const rendered = renderApp({ route: `/projects/${project.id}`, services });
  await screen.findAllByRole('heading', { level: 1, name: 'Maker Market' });
  await rendered.user.click(screen.getByRole('tab', { name: 'Plan' }));
  return rendered;
}

describe('Plan tab', () => {
  it('explains that planning needs API mode instead of simulating it', async () => {
    await openPlan(null);
    expect(screen.getByText('Planning needs API mode')).toBeInTheDocument();
    const agents = screen.getByRole('region', { name: 'Agent activity' });
    expect(within(agents).getAllByText('Planned')).toHaveLength(10);
    expect(within(agents).queryByText('Available')).not.toBeInTheDocument();
  });

  it('starts planning and reuses the idempotency key when a retry is needed', async () => {
    const runs = fakeRuns(null);
    const start = runs.startPlanning as ReturnType<typeof vi.fn>;
    const original = start.getMockImplementation()!;
    start.mockImplementationOnce(async () => {
      throw new AppError('network', 'Cannot reach the Omniora API.');
    });
    const { user } = await openPlan(runs);
    expect(await screen.findByText('No plan yet')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Start planning' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach the Omniora API.');
    start.mockImplementation(original);
    await user.click(screen.getByRole('button', { name: 'Start planning' }));
    expect(await screen.findByText('Waiting for a worker…')).toBeInTheDocument();
    const keys = start.mock.calls.map((call) => call[1]);
    expect(keys).toHaveLength(2);
    expect(keys[0]).toBe(keys[1]);
  });

  it('shows the persisted plan and records an approval for the exact version', async () => {
    const runs = fakeRuns(awaitingDetail());
    const { user } = await openPlan(runs);
    expect(await screen.findByText('A storefront for makers with hosted checkout.')).toBeInTheDocument();
    const questions = screen.getByRole('region', { name: 'Open questions' });
    expect(within(questions).getByText('Which payment provider?')).toBeInTheDocument();
    expect(within(questions).getByText('Blocking')).toBeInTheDocument();
    const tasks = screen.getByRole('region', { name: 'Proposed tasks (2)' });
    expect(within(tasks).getAllByText('Proposed, not started')).toHaveLength(2);
    expect(within(tasks).getByText(/Depends on T1/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Approve plan' }));
    const dialog = screen.getByRole('dialog', { name: 'Approve plan v1?' });
    await user.click(within(dialog).getByRole('button', { name: 'Approve plan' }));
    expect(runs.decide).toHaveBeenCalledWith('run-1', 'ap-1', { decision: 'approve', planVersion: 1 });
    expect(await screen.findByText('Approved')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve plan' })).not.toBeInTheDocument();
  });

  it('requires a comment to request a revision', async () => {
    const runs = fakeRuns(awaitingDetail());
    const { user } = await openPlan(runs);
    await user.click(await screen.findByRole('button', { name: 'Request changes' }));
    const submit = screen.getByRole('button', { name: 'Request revision' });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText('What should change?'), 'Add gift cards');
    await user.click(submit);
    expect(runs.decide).toHaveBeenCalledWith('run-1', 'ap-1', { decision: 'revise', planVersion: 1, comment: 'Add gift cards' });
  });

  it('shows streamed run events in the activity panel', async () => {
    const runs = fakeRuns({ run: runRecord({ state: 'planning', currentPlanVersion: null }), plan: null, tasks: [], approvals: [], attempts: [] });
    await openPlan(runs);
    await screen.findByText('The Project Manager agent is working on the plan…');
    runs.emit({ seq: 8, type: 'plan.created', data: { plan_version: 1, task_count: 3 }, at });
    const agents = screen.getByRole('region', { name: 'Agent activity' });
    expect(await within(agents).findByText('Plan v1 created with 3 proposed tasks')).toBeInTheDocument();
    expect(within(agents).getByText('Available')).toBeInTheDocument();
  });

  it('shows a failed run with its persisted reason', async () => {
    await openPlan(
      fakeRuns({
        run: runRecord({ state: 'failed', currentPlanVersion: null, failureCode: 'invalid-plan',
          failureMessage: 'The agent did not produce a valid plan after 3 attempts.' }),
        plan: null, tasks: [], approvals: [], attempts: [],
      }),
    );
    expect(await screen.findByText('Planning failed')).toBeInTheDocument();
    expect(screen.getByText('The agent did not produce a valid plan after 3 attempts.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start a new plan' })).toBeInTheDocument();
  });
});
