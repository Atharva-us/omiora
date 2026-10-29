import { useId, useState, type ReactNode } from 'react';
import { Check, CircleDot, ClipboardList, Flag, ListTodo, RotateCcw, Square, X } from 'lucide-react';
import { LoadErrorNotice } from '@/components/feedback/LoadErrorNotice';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { TextAreaField } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { Notice } from '@/components/ui/Notice';
import { LoadingBlock, Spinner } from '@/components/ui/Spinner';
import { technologyNames } from '@/domain/projects/catalog';
import { isTerminalRunState, pendingApproval, type RunDetail } from '@/domain/runs/run';
import { useServices } from '@/hooks/use-services';
import { AGENT_LABELS, RUN_STATE_META } from '../run/run-model';
import type { ProjectRun } from '../run/use-project-run';

const STREAM_LABELS = {
  idle: null,
  connecting: 'Connecting to live updates…',
  open: 'Live updates connected',
  reconnecting: 'Live updates interrupted. Reconnecting…',
  closed: 'Live updates closed',
} as const;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title}>
      <h3 className="text-[0.6875rem] font-semibold tracking-[0.12em] text-faint uppercase">{title}</h3>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function AttemptList({ detail }: { detail: RunDetail }) {
  if (detail.attempts.length === 0) return null;
  return (
    <Section title="Agent attempts">
      <ol className="divide-y divide-line-soft rounded-lg border border-line bg-surface text-sm">
        {detail.attempts.map((attempt) => (
          <li key={`${attempt.planVersion}-${attempt.attempt}`} className="px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-faint">
                v{attempt.planVersion} · #{attempt.attempt}
              </span>
              <Badge tone={attempt.outcome === 'succeeded' ? 'success' : attempt.outcome === 'invalid-output' ? 'warning' : 'danger'}>
                {attempt.outcome}
              </Badge>
              <span className="text-xs text-faint">{attempt.model}</span>
              {attempt.outputTokens !== null && (
                <span className="text-xs text-faint">
                  {attempt.inputTokens ?? '?'} in / {attempt.outputTokens} out tokens
                </span>
              )}
            </div>
            {attempt.errorMessage && <p className="mt-1 text-[0.8125rem] text-muted">{attempt.errorMessage}</p>}
            {attempt.validationErrors.length > 0 && (
              <ul className="mt-1 list-disc pl-5 text-[0.8125rem] text-muted">
                {attempt.validationErrors.slice(0, 5).map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>
    </Section>
  );
}

function PlanView({ detail }: { detail: RunDetail }) {
  const plan = detail.plan;
  if (!plan) return null;
  const { content } = plan;
  return (
    <div className="space-y-6">
      <Section title={`Plan v${plan.version}: summary`}>
        <p className="text-sm leading-relaxed whitespace-pre-line text-ink">{content.summary}</p>
      </Section>

      {content.openQuestions.length > 0 && (
        <Section title="Open questions">
          <ul className="space-y-2">
            {content.openQuestions.map((question) => (
              <li key={question.id} className="rounded-lg border border-line bg-surface p-3">
                <div className="flex items-start gap-2">
                  <span className="font-mono text-xs text-faint">{question.id}</span>
                  <p className="flex-1 text-sm text-ink">{question.question}</p>
                  {question.blocking && <Badge tone="warning">Blocking</Badge>}
                </div>
                <p className="mt-1 pl-7 text-[0.8125rem] text-muted">{question.whyItMatters}</p>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {content.flaggedRequirements.length > 0 && (
        <Section title="Flagged requirements">
          <Notice tone="warning" className="mb-3">
            These approved must-haves are not covered by any task. The Project Manager gave a reason for each.
          </Notice>
          <ul className="space-y-2">
            {content.flaggedRequirements.map((flag) => (
              <li key={flag.id} className="flex items-start gap-2 rounded-lg border border-line bg-surface p-3 text-sm">
                <Flag aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-warning" />
                <span className="font-mono text-xs text-faint">{flag.id}</span>
                <span className="flex-1 text-ink">{flag.reason}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {content.requirements.length > 0 && (
        <Section title={detail.requirements ? 'Derived requirements (added by the Project Manager)' : 'Requirements'}>
          <ul className="divide-y divide-line-soft rounded-lg border border-line bg-surface">
            {content.requirements.map((requirement) => (
              <li key={requirement.id} className="flex items-start gap-3 px-4 py-2.5 text-sm">
                <span className="font-mono text-xs text-faint">{requirement.id}</span>
                <span className="flex-1 text-ink">{requirement.statement}</span>
                <Badge tone={requirement.priority === 'must' ? 'info' : 'neutral'}>{requirement.priority}</Badge>
                {requirement.source === 'inferred' && <Badge>inferred</Badge>}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {content.assumptions.length > 0 && (
        <Section title="Assumptions">
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
            {content.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        </Section>
      )}

      {content.recommendedStack.technologies.length > 0 && (
        <Section title="Recommended stack">
          <div className="flex flex-wrap gap-1.5">
            {technologyNames(content.recommendedStack.technologies).map((name) => (
              <Badge key={name}>{name}</Badge>
            ))}
          </div>
          <p className="mt-2 text-sm text-muted">{content.recommendedStack.rationale}</p>
        </Section>
      )}

      <Section title={`Proposed tasks (${detail.tasks.length})`}>
        <Notice tone="info" className="mb-3">
          These are proposals for future specialist agents. None has started, and none will run in this phase.
        </Notice>
        <ol className="space-y-3">
          {detail.tasks.map((task) => (
            <li key={task.key} className="rounded-lg border border-line bg-surface p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-faint">{task.key}</span>
                <h4 className="flex-1 text-sm font-semibold text-ink">{task.title}</h4>
                <Badge>{AGENT_LABELS[task.suggestedAgent]}</Badge>
                <span className="inline-flex items-center gap-1 text-xs text-faint">
                  <Square aria-hidden="true" className="size-3" />
                  Proposed, not started
                </span>
              </div>
              <p className="mt-2 text-sm text-muted">{task.description}</p>
              <ul className="mt-2 space-y-1 text-[0.8125rem] text-muted">
                {task.acceptanceCriteria.map((criterion) => (
                  <li key={criterion} className="flex gap-2">
                    <CircleDot aria-hidden="true" className="mt-0.5 size-3 shrink-0 text-faint" />
                    {criterion}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-faint">
                {task.dependsOn.length > 0 ? `Depends on ${task.dependsOn.join(', ')}` : 'No dependencies'} · Covers{' '}
                {task.requirementIds.join(', ')}
              </p>
            </li>
          ))}
        </ol>
      </Section>
    </div>
  );
}

function DecisionControls({ run }: { run: ProjectRun }) {
  const detail = run.detail;
  const [mode, setMode] = useState<'idle' | 'confirm-approve' | 'revise' | 'reject'>('idle');
  const [comment, setComment] = useState('');
  const commentId = useId();
  const approval = detail ? pendingApproval(detail) : null;
  if (!detail || !approval) return null;

  const submit = async (decision: 'approve' | 'reject' | 'revise') => {
    await run.decide(decision, comment.trim() || undefined);
    setMode('idle');
    setComment('');
  };

  return (
    <section aria-labelledby={`${commentId}-title`} className="rounded-xl border border-warning/30 bg-warning/[0.05] p-4">
      <h3 id={`${commentId}-title`} className="text-sm font-semibold text-ink">
        Your decision on plan v{approval.planVersion}
      </h3>
      <p className="mt-1 text-[0.8125rem] text-muted">
        Approving records your consent to this plan. No code is written or run in this phase.
      </p>
      {mode === 'revise' || mode === 'reject' ? (
        <div className="mt-3 space-y-3">
          <TextAreaField
            label={mode === 'revise' ? 'What should change?' : 'Reason (optional)'}
            rows={3}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            maxLength={2000}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant={mode === 'reject' ? 'danger' : 'primary'}
              loading={run.busy}
              disabled={mode === 'revise' && !comment.trim()}
              onClick={() => submit(mode)}
            >
              {mode === 'revise' ? 'Request revision' : 'Reject plan'}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setMode('idle')}>
              Back
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" onClick={() => setMode('confirm-approve')} disabled={run.busy}>
            <Check aria-hidden="true" />
            Approve plan
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setMode('revise')} disabled={run.busy}>
            <RotateCcw aria-hidden="true" />
            Request changes
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setMode('reject')} disabled={run.busy}>
            <X aria-hidden="true" />
            Reject
          </Button>
        </div>
      )}
      <Modal
        open={mode === 'confirm-approve'}
        onClose={() => setMode('idle')}
        title={`Approve plan v${approval.planVersion}?`}
        description="This records your approval of this exact plan version."
        footer={
          <>
            <Button variant="secondary" onClick={() => setMode('idle')}>
              Cancel
            </Button>
            <Button onClick={() => submit('approve')} loading={run.busy} data-autofocus>
              Approve plan
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">
          The proposed tasks stay proposals: the agents that would carry them out are not built yet, so nothing will be
          generated or executed.
        </p>
      </Modal>
    </section>
  );
}

/** How a plan can be started: from approved requirements, or by explicitly skipping them. */
function StartPlanningActions({ run, onOpenRequirements, label }: { run: ProjectRun; onOpenRequirements: () => void; label?: string }) {
  const [confirmSkip, setConfirmSkip] = useState(false);
  const approved = run.approvedRequirements;
  return (
    <div className="flex flex-wrap justify-center gap-2">
      {approved ? (
        <Button onClick={() => run.start()} loading={run.busy}>
          {label ?? 'Start planning'} from requirements v{approved.version.version}
        </Button>
      ) : (
        <Button onClick={onOpenRequirements}>
          <ListTodo aria-hidden="true" />
          Go to requirements
        </Button>
      )}
      <Button variant="ghost" onClick={() => setConfirmSkip(true)} disabled={run.busy}>
        Plan without requirements
      </Button>
      <Modal
        open={confirmSkip}
        onClose={() => setConfirmSkip(false)}
        title="Plan without approved requirements?"
        description="The run is recorded as planned without requirements."
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmSkip(false)}>
              Cancel
            </Button>
            <Button
              data-autofocus
              loading={run.busy}
              onClick={async () => {
                await run.start({ withoutRequirements: true });
                setConfirmSkip(false);
              }}
            >
              Plan without requirements
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">
          The Project Manager will work from the brief and notes only. Nothing marks the requirements step as done, and the
          plan is labelled accordingly.
        </p>
      </Modal>
    </div>
  );
}

function PlanBasis({ detail }: { detail: RunDetail }) {
  if (detail.requirements) {
    return (
      <p className="mt-1 text-xs text-faint">
        Follows approved requirements v{detail.requirements.version} · sha256{' '}
        <span className="font-mono">{detail.requirements.contentSha256.slice(0, 12)}</span>…
      </p>
    );
  }
  if (detail.run.requirementsSkipped) {
    return (
      <Badge tone="warning" className="mt-1.5">
        Planned without approved requirements
      </Badge>
    );
  }
  return null;
}

interface PlanPanelProps {
  run: ProjectRun;
  isSample: boolean;
  onOpenRequirements: () => void;
}

export function PlanPanel({ run, isSample, onOpenRequirements }: PlanPanelProps) {
  const { mode } = useServices();
  if (isSample) {
    return (
      <div className="p-5 sm:p-6">
        <Notice tone="warning" title="Sample projects cannot be planned">
          Create your own project to run the Project Manager agent.
        </Notice>
      </div>
    );
  }
  if (!run.available) {
    return (
      <div className="p-5 sm:p-6">
        <Notice tone="info" title="Planning needs API mode">
          {mode === 'demo'
            ? 'This build is in demo mode, with no backend, so the Project Manager agent cannot run. Nothing is simulated.'
            : 'Planning is not available for this project.'}
        </Notice>
      </div>
    );
  }
  if (run.loadError) {
    return (
      <div className="p-5 sm:p-6">
        <LoadErrorNotice title="The plan could not be loaded" message={run.loadError.message} code={run.loadError.code} onRetry={run.reload} />
      </div>
    );
  }
  if (run.isLoading) return <LoadingBlock label="Loading plan" />;

  const detail = run.detail;
  const actionError = run.actionError && (
    <Notice tone="danger" role="alert">
      {run.actionError}
    </Notice>
  );

  if (!detail) {
    return (
      <div className="space-y-4 p-5 sm:p-6">
        {actionError}
        <EmptyState
          icon={ClipboardList}
          title="No plan yet"
          action={<StartPlanningActions run={run} onOpenRequirements={onOpenRequirements} />}
        >
          {run.approvedRequirements
            ? `The Project Manager plans from approved requirements v${run.approvedRequirements.version.version}: every task references their ids, and every must-have is covered or flagged with a reason. It does not write or run code.`
            : 'Planning starts from requirements you approve. Run the Requirements Analyst first, or explicitly plan without requirements. The Project Manager does not write or run code.'}
        </EmptyState>
      </div>
    );
  }

  const state = detail.run.state;
  const meta = RUN_STATE_META[state];
  const terminal = isTerminalRunState(state);
  const streamLabel = STREAM_LABELS[run.stream];

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-5 sm:p-6">
      <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Badge tone={meta.tone} dot>
              {meta.label}
            </Badge>
            {detail.run.currentPlanVersion !== null && (
              <span className="font-mono text-xs text-faint">plan v{detail.run.currentPlanVersion}</span>
            )}
          </div>
          <p className="mt-1.5 text-[0.8125rem] text-muted">{meta.description}</p>
          <PlanBasis detail={detail} />
          {streamLabel && (
            <p role="status" className="mt-1 text-xs text-faint">
              {streamLabel}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {!terminal && (
            <Button size="sm" variant="secondary" onClick={run.cancel} loading={run.busy}>
              Cancel run
            </Button>
          )}
          {terminal && <StartPlanningActions run={run} onOpenRequirements={onOpenRequirements} label="New plan" />}
        </div>
      </div>

      {actionError}

      {(state === 'queued' || state === 'planning') && (
        <div role="status" className="flex items-center gap-2 text-sm text-muted">
          <Spinner />
          {state === 'queued' ? 'Waiting for a worker…' : 'The Project Manager agent is working on the plan…'}
        </div>
      )}

      {state === 'failed' && (
        <Notice tone="danger" title="Planning failed">
          {detail.run.failureMessage ?? 'The agent did not produce a valid plan.'}
        </Notice>
      )}

      <DecisionControls run={run} />
      <PlanView detail={detail} />
      <AttemptList detail={detail} />
    </div>
  );
}
