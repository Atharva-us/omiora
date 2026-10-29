import { screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AppError } from '@/domain/errors';
import {
  sessionDetailSchema,
  type Question,
  type RequirementsSession,
  type RequirementsVersion,
  type SessionDetail,
} from '@/domain/requirements/requirements';
import type { RequirementsService } from '@/services/contracts/requirements-service';
import { validConfiguration } from '@/test/fixtures';
import { createTestServices, renderApp } from '@/test/render-app';
import { changedAnswers, initialDrafts } from './requirements/requirements-model';

const at = '2026-10-29T12:00:00.000Z';

function session(overrides: Partial<RequirementsSession> = {}): RequirementsSession {
  return {
    id: 'session-1', projectId: 'p', state: 'discovering', failureCode: null, failureMessage: null, lastEventSeq: 7,
    createdAt: at, updatedAt: at, ...overrides,
  };
}

function question(overrides: Partial<Question> = {}): Question {
  return {
    key: 'DQ-001', turnNumber: 1, prompt: 'Which payment methods must checkout accept?', why: 'Decides the payment integration.',
    kind: 'multiple-choice', options: ['Cards', 'PayPal', 'Bank transfer'], blocking: true, topic: 'scope', relatesTo: [],
    status: 'open', answer: null, ...overrides,
  };
}

function version(overrides: Partial<RequirementsVersion> = {}): RequirementsVersion {
  return {
    id: 'version-1', version: 1, parentVersionId: null, contentSha256: 'c'.repeat(64), turnNumber: 1, createdAt: at,
    frozenAt: null, approvedAt: null, requirementCount: 2, mustCount: 1, ready: false, diff: null,
    content: {
      schemaVersion: 1,
      context: {
        goal: 'Let makers sell handmade goods online.', scope: 'Storefront and checkout.', platform: 'website', deployment: '',
        personas: [{ name: 'Shopper', description: 'Buys goods.' }], tenancy: 'single', constraints: [], integrations: [],
        outOfScope: ['Marketplace for other shops'],
      },
      requirements: [
        { id: 'REQ-001', statement: 'Shoppers can browse products by category.', kind: 'functional', priority: 'must',
          confidence: 'high', source: 'brief', evidence: ['brief:description'], acceptanceCriteria: ['A category page lists its products.'],
          tags: [], status: 'active', deprecationReason: '' },
        { id: 'REQ-002', statement: 'Shoppers can save favourites.', kind: 'functional', priority: 'could',
          confidence: 'low', source: 'inferred', evidence: [], acceptanceCriteria: ['A saved product appears in favourites.'],
          tags: [], status: 'active', deprecationReason: '' },
      ],
      assumptions: [{ statement: 'One currency at launch.', confidence: 'medium', basis: [] }],
      openQuestions: [{ key: 'DQ-001', prompt: 'Which payment methods must checkout accept?', blocking: true, topic: 'scope', status: 'open' }],
      readiness: { ready: false, blockers: ['Blocking question DQ-001 is unanswered.'] },
      decisions: [],
    },
    ...overrides,
  };
}

function detail(overrides: Partial<SessionDetail> = {}): SessionDetail {
  return {
    session: session(),
    turn: { number: 1, status: 'completed', trigger: 'start', tries: 1, failureCode: null, failureMessage: null,
      requirementsVersion: 1, createdAt: at, completedAt: at },
    maxTurns: 8,
    questions: [question()],
    version: version(),
    approvals: [],
    attempts: [],
    ...overrides,
  };
}

function fakeRequirements(initial: SessionDetail | null) {
  let current = initial;
  const service: RequirementsService & { set: (next: SessionDetail) => void } = {
    available: true,
    listSessions: vi.fn(async () => (current ? [current.session] : [])),
    getSession: vi.fn(async () => {
      if (!current) throw new AppError('not-found', 'No session.');
      return current;
    }),
    startSession: vi.fn(async () => {
      current = detail({
        session: session({ state: 'queued' }),
        turn: { number: 1, status: 'queued', trigger: 'start', tries: 1, failureCode: null, failureMessage: null,
          requirementsVersion: null, createdAt: at, completedAt: null },
        questions: [],
        version: null,
      });
      return current.session;
    }),
    submitAnswers: vi.fn(async () => current!),
    retryTurn: vi.fn(async () => current!),
    submitForApproval: vi.fn(async () => current!),
    decide: vi.fn(async () => current!),
    cancel: vi.fn(async () => current!),
    listVersions: vi.fn(async () => []),
    getVersion: vi.fn(async () => version()),
    getApproved: vi.fn(async () => null),
    set: (next) => {
      current = next;
    },
  };
  return service;
}

async function openRequirements(requirements: RequirementsService | null) {
  const base = createTestServices();
  const services = requirements
    ? { ...base, requirements, runs: { ...base.runs, available: true, listRuns: vi.fn(async () => []), subscribe: vi.fn(() => () => {}) } }
    : base;
  const project = await services.projects.createProject(validConfiguration({ name: 'Maker Market' }));
  const rendered = renderApp({ route: `/projects/${project.id}`, services });
  await screen.findAllByRole('heading', { level: 1, name: 'Maker Market' });
  await rendered.user.click(screen.getByRole('tab', { name: 'Requirements' }));
  return rendered;
}

describe('Requirements tab', () => {
  it('is honest in demo mode: nothing is simulated', async () => {
    await openRequirements(null);
    expect(screen.getByText('Requirements discovery needs API mode')).toBeInTheDocument();
    expect(screen.getByText(/No questions or requirements are simulated/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Start requirements discovery/ })).not.toBeInTheDocument();
  });

  it('starts a session and shows analysing only while the server reports a queued turn', async () => {
    const requirements = fakeRequirements(null);
    const { user } = await openRequirements(requirements);
    expect(await screen.findByText('No requirements yet')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Start requirements discovery' }));
    expect(await screen.findByText('Turn 1 is waiting for a worker…')).toBeInTheDocument();
    expect(requirements.startSession).toHaveBeenCalledWith(expect.any(String), expect.stringMatching(/^discovery-/));
  });

  it('answers questions with the right controls, including "I don\'t know"', async () => {
    const requirements = fakeRequirements(
      detail({
        questions: [
          question(),
          question({ key: 'DQ-002', prompt: 'Is there a launch deadline?', kind: 'yes-no', options: [], blocking: false }),
          question({ key: 'DQ-003', prompt: 'How long must orders be kept?', kind: 'single-choice', options: ['1 year', '7 years'] }),
        ],
      }),
    );
    const { user } = await openRequirements(requirements);
    await user.click(await screen.findByRole('checkbox', { name: 'Cards' }));
    await user.click(screen.getByRole('checkbox', { name: 'PayPal' }));
    await user.click(screen.getByRole('radio', { name: 'No' }));
    const retention = screen.getByText('How long must orders be kept?', { selector: 'p' }).closest('li')!;
    await user.click(within(retention).getByRole('checkbox', { name: "I don't know" }));
    expect(within(retention).getByRole('radio', { name: '7 years' })).toBeDisabled();
    expect(within(retention).getByText(/Recorded as unknown, never as an answer/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Send answers to the analyst' }));
    expect(requirements.submitAnswers).toHaveBeenCalledWith(
      'session-1',
      expect.stringMatching(/^answers-/),
      [
        { questionKey: 'DQ-001', value: ['Cards', 'PayPal'] },
        { questionKey: 'DQ-002', value: false },
        { questionKey: 'DQ-003', unknown: true },
      ],
      true,
    );
  });

  it('retries a failed submission with the same idempotency key', async () => {
    const requirements = fakeRequirements(detail());
    const submit = requirements.submitAnswers as ReturnType<typeof vi.fn>;
    submit.mockImplementationOnce(async () => {
      throw new AppError('network', 'Cannot reach the Omniora API.');
    });
    const { user } = await openRequirements(requirements);
    await user.click(await screen.findByRole('checkbox', { name: 'Cards' }));
    await user.click(screen.getByRole('button', { name: 'Send answers to the analyst' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach the Omniora API.');
    await user.click(screen.getByRole('button', { name: 'Send answers to the analyst' }));
    const keys = submit.mock.calls.map((call) => call[1]);
    expect(keys).toHaveLength(2);
    expect(keys[0]).toBe(keys[1]);
  });

  it('resumes after a refresh with the saved answers and shows structured requirements', async () => {
    const answered = question({ status: 'answered', answer: { value: ['PayPal'], unknown: false, answeredAt: at } });
    await openRequirements(fakeRequirements(detail({ questions: [answered] })));
    expect(await screen.findByRole('checkbox', { name: 'PayPal' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Cards' })).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Ask the analyst to continue' })).toBeInTheDocument();

    const must = screen.getByRole('region', { name: 'Must have (1)' });
    expect(within(must).getByText('REQ-001')).toBeInTheDocument();
    expect(within(must).getByText('high confidence')).toBeInTheDocument();
    expect(within(must).getByText(/From the brief · brief:description/)).toBeInTheDocument();
    expect(within(must).getByText('A category page lists its products.')).toBeInTheDocument();
    const could = screen.getByRole('region', { name: 'Could have (1)' });
    expect(within(could).getByText(/Inferred by the analyst/)).toBeInTheDocument();
    const blockers = screen.getByRole('region', { name: 'Outstanding blockers' });
    expect(within(blockers).getByText('Blocking question DQ-001 is unanswered.')).toBeInTheDocument();
  });

  it('shows a failed turn with its reason and retries it', async () => {
    const requirements = fakeRequirements(
      detail({
        turn: { number: 2, status: 'failed', trigger: 'answers', tries: 1, failureCode: 'provider-unavailable',
          failureMessage: 'The model provider failed repeatedly. Retry the turn later.', requirementsVersion: null,
          createdAt: at, completedAt: at },
      }),
    );
    const { user } = await openRequirements(requirements);
    expect(await screen.findByText('Turn 2 failed')).toBeInTheDocument();
    expect(screen.getByText(/The model provider failed repeatedly.*Your answers are kept/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry turn' }));
    expect(requirements.retryTurn).toHaveBeenCalledWith('session-1');
  });

  it('submits a ready version, then approves it or requests changes with a comment', async () => {
    const ready = detail({ session: session({ state: 'ready-for-review' }), version: version({ version: 2, ready: true }) });
    const awaiting: SessionDetail = {
      ...ready,
      session: session({ state: 'awaiting-approval' }),
      version: version({ version: 2, ready: true, frozenAt: at }),
      approvals: [{ id: 'ap-1', version: 2, gate: 'requirements', status: 'pending', comment: null, decidedAt: null, createdAt: at }],
    };
    const requirements = fakeRequirements(ready);
    (requirements.submitForApproval as ReturnType<typeof vi.fn>).mockImplementation(async () => {
      requirements.set(awaiting); // the server froze the version and opened the approval gate
      return awaiting;
    });
    const { user } = await openRequirements(requirements);
    await user.click(await screen.findByRole('button', { name: 'Submit v2 for approval' }));
    expect(requirements.submitForApproval).toHaveBeenCalledWith('session-1', 2);
    expect(await screen.findByText('Your decision on requirements v2')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Request changes' }));
    const send = screen.getByRole('button', { name: 'Request changes' });
    expect(send).toBeDisabled();
    await user.type(screen.getByLabelText('What should change?'), 'Add gift cards');
    await user.click(send);
    expect(requirements.decide).toHaveBeenCalledWith('session-1', 'ap-1', { decision: 'request-changes', version: 2, comment: 'Add gift cards' });

    await user.click(await screen.findByRole('button', { name: 'Approve requirements' }));
    const dialog = screen.getByRole('dialog', { name: 'Approve requirements v2?' });
    await user.click(within(dialog).getByRole('button', { name: 'Approve requirements' }));
    expect(requirements.decide).toHaveBeenLastCalledWith('session-1', 'ap-1', { decision: 'approve', version: 2 });
  });

  it('hands approved requirements over to the Plan tab', async () => {
    const approved = detail({
      session: session({ state: 'approved' }),
      questions: [question({ status: 'answered', answer: { value: ['Cards'], unknown: false, answeredAt: at } })],
      version: version({ version: 2, ready: true, frozenAt: at, approvedAt: at }),
    });
    const { user } = await openRequirements(fakeRequirements(approved));
    expect(await screen.findByText('Requirements v2 approved')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Cards' })).toBeDisabled(); // approved versions are final
    await user.click(screen.getByRole('button', { name: 'Plan from these requirements' }));
    expect(screen.getByRole('tab', { name: 'Plan' })).toHaveAttribute('aria-selected', 'true');
  });

  it('shows version history with the changes between versions', async () => {
    const requirements = fakeRequirements(detail({ version: version({ version: 2 }) }));
    (requirements.listVersions as ReturnType<typeof vi.fn>).mockResolvedValue([
      { ...version(), content: undefined, diff: undefined },
      { ...version({ id: 'version-2', version: 2 }), content: undefined, diff: undefined },
    ]);
    (requirements.getVersion as ReturnType<typeof vi.fn>).mockResolvedValue(
      version({ version: 2, diff: { fromVersion: 1, added: ['REQ-002'], deprecated: [], changed: [{ id: 'REQ-001', fields: ['acceptance_criteria'] }], contextFields: [] } }),
    );
    const { user } = await openRequirements(requirements);
    const history = await screen.findByRole('region', { name: 'Version history' });
    await user.click(within(history).getByRole('button', { name: 'Show changes' }));
    expect(await within(history).findByText('Added: REQ-002')).toBeInTheDocument();
    expect(within(history).getByText('Changed REQ-001: acceptance criteria')).toBeInTheDocument();
    expect(requirements.getVersion).toHaveBeenCalledWith('session-1', 2, 1);
  });
});

describe('requirements model and schemas', () => {
  it('sends only complete answers that changed', () => {
    const questions = [
      question({ status: 'answered', answer: { value: ['Cards'], unknown: false, answeredAt: at } }),
      question({ key: 'DQ-002', kind: 'free-text', options: [] }),
      question({ key: 'DQ-003', kind: 'single-choice', options: ['A', 'B'] }),
    ];
    const drafts = { ...initialDrafts(questions), 'DQ-002': { value: '  ', unknown: false }, 'DQ-003': { value: 'B', unknown: false } };
    expect(changedAnswers(questions, drafts)).toEqual([{ questionKey: 'DQ-003', value: 'B' }]);
    expect(changedAnswers(questions, { ...drafts, 'DQ-001': { value: undefined, unknown: true } })).toContainEqual({
      questionKey: 'DQ-001',
      unknown: true,
    });
  });

  it('parses a session detail and rejects unknown states', () => {
    expect(sessionDetailSchema.safeParse(detail()).success).toBe(true);
    expect(sessionDetailSchema.safeParse({ ...detail(), session: { ...session(), state: 'executing' } }).success).toBe(false);
  });
});
