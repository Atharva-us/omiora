import { useId, useState } from 'react';
import { ArrowRight, Check, ListTodo, RotateCcw } from 'lucide-react';
import { LoadErrorNotice } from '@/components/feedback/LoadErrorNotice';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { TextAreaField } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { Notice } from '@/components/ui/Notice';
import { LoadingBlock, Spinner } from '@/components/ui/Spinner';
import {
  isAnalysing,
  isTerminalSessionState,
  pendingRequirementsApproval,
  type SessionDetail,
} from '@/domain/requirements/requirements';
import { useServices } from '@/hooks/use-services';
import { QuestionCard } from './QuestionCard';
import { RequirementsDocumentView, Section } from './RequirementsDocumentView';
import { changedAnswers, initialDrafts, SESSION_STATE_META, type AnswerDrafts } from './requirements-model';
import type { RequirementsSessionState } from './use-requirements-session';
import { VersionHistory } from './VersionHistory';

const STREAM_LABELS = {
  idle: null,
  connecting: 'Connecting to live updates…',
  open: 'Live updates connected',
  reconnecting: 'Live updates interrupted. Reconnecting…',
  closed: 'Live updates closed',
} as const;

/** Identifies the answers the server has recorded. Keying `Questions` by it restarts the drafts
 * from the server whenever those answers change (a new turn, another tab, a reload). */
const answersSignature = (detail: SessionDetail) =>
  JSON.stringify([detail.session.state, detail.questions.map((q) => [q.key, q.status, q.answer?.answeredAt ?? null])]);

function Questions({ discovery, detail }: { discovery: RequirementsSessionState; detail: SessionDetail }) {
  const questions = detail.questions.filter((q) => q.status !== 'withdrawn');
  const [drafts, setDrafts] = useState<AnswerDrafts>(() => initialDrafts(questions));

  const state = detail.session.state;
  const editable = (state === 'discovering' || state === 'ready-for-review') && !isAnalysing(detail);
  const failed = detail.turn?.status === 'failed';
  const changes = changedAnswers(questions, drafts);
  const unanswered = questions.filter((q) => !q.answer);
  if (questions.length === 0) return null;

  return (
    <Section title={`Questions (${unanswered.length} open)`}>
      <ol className="space-y-3">
        {questions.map((question) => (
          <QuestionCard
            key={question.key}
            question={question}
            draft={drafts[question.key]}
            disabled={!editable || discovery.busy}
            onChange={(draft) => setDrafts((previous) => ({ ...previous, [question.key]: draft }))}
          />
        ))}
      </ol>
      {editable && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            onClick={() => discovery.saveAnswers(changes, true)}
            loading={discovery.busy}
            disabled={failed || (changes.length === 0 && state !== 'discovering')}
          >
            <ArrowRight aria-hidden="true" />
            {changes.length > 0 ? 'Send answers to the analyst' : 'Ask the analyst to continue'}
          </Button>
          {state === 'discovering' && (
            <Button size="sm" variant="secondary" onClick={() => discovery.saveAnswers(changes, false)} disabled={changes.length === 0 || discovery.busy}>
              Save without sending
            </Button>
          )}
          {state === 'ready-for-review' && changes.length > 0 && (
            <p className="text-xs text-faint">Changing an answer reopens discovery so the analyst can update the requirements.</p>
          )}
        </div>
      )}
    </Section>
  );
}

function ApprovalControls({ discovery, detail }: { discovery: RequirementsSessionState; detail: SessionDetail }) {
  const [mode, setMode] = useState<'idle' | 'confirm' | 'changes'>('idle');
  const [comment, setComment] = useState('');
  const titleId = useId();
  const approval = pendingRequirementsApproval(detail);
  if (!approval) return null;
  return (
    <section aria-labelledby={titleId} className="rounded-xl border border-warning/30 bg-warning/[0.05] p-4">
      <h3 id={titleId} className="text-sm font-semibold text-ink">
        Your decision on requirements v{approval.version}
      </h3>
      <p className="mt-1 text-[0.8125rem] text-muted">
        Approving makes this exact version immutable and lets the Project Manager plan from it.
      </p>
      {mode === 'changes' ? (
        <div className="mt-3 space-y-3">
          <TextAreaField label="What should change?" rows={3} maxLength={2000} value={comment} onChange={(e) => setComment(e.target.value)} />
          <div className="flex gap-2">
            <Button
              size="sm"
              loading={discovery.busy}
              disabled={!comment.trim()}
              onClick={async () => {
                await discovery.decide('request-changes', comment.trim());
                setMode('idle');
                setComment('');
              }}
            >
              Request changes
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setMode('idle')}>
              Back
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" onClick={() => setMode('confirm')} disabled={discovery.busy}>
            <Check aria-hidden="true" />
            Approve requirements
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setMode('changes')} disabled={discovery.busy}>
            <RotateCcw aria-hidden="true" />
            Request changes
          </Button>
        </div>
      )}
      <Modal
        open={mode === 'confirm'}
        onClose={() => setMode('idle')}
        title={`Approve requirements v${approval.version}?`}
        description="This records your approval of this exact, frozen version."
        footer={
          <>
            <Button variant="secondary" onClick={() => setMode('idle')}>
              Cancel
            </Button>
            <Button
              data-autofocus
              loading={discovery.busy}
              onClick={async () => {
                await discovery.decide('approve');
                setMode('idle');
              }}
            >
              Approve requirements
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">Approved requirements cannot be edited. To change them later, start a new discovery session.</p>
      </Modal>
    </section>
  );
}

interface RequirementsPanelProps {
  discovery: RequirementsSessionState;
  isSample: boolean;
  onOpenPlan: () => void;
}

export function RequirementsPanel({ discovery, isSample, onOpenPlan }: RequirementsPanelProps) {
  const { mode } = useServices();
  if (isSample) {
    return (
      <div className="p-5 sm:p-6">
        <Notice tone="warning" title="Sample projects have no requirements session">
          Create your own project to run the Requirements Analyst.
        </Notice>
      </div>
    );
  }
  if (!discovery.available) {
    return (
      <div className="p-5 sm:p-6">
        <Notice tone="info" title="Requirements discovery needs API mode">
          {mode === 'demo'
            ? 'This build is in demo mode, with no backend, so the Requirements Analyst cannot run. No questions or requirements are simulated.'
            : 'Requirements discovery is not available for this project.'}
        </Notice>
      </div>
    );
  }
  if (discovery.loadError) {
    return (
      <div className="p-5 sm:p-6">
        <LoadErrorNotice
          title="The requirements could not be loaded"
          message={discovery.loadError.message}
          code={discovery.loadError.code}
          onRetry={discovery.reload}
        />
      </div>
    );
  }
  if (discovery.isLoading) return <LoadingBlock label="Loading requirements" />;

  const actionError = discovery.actionError && (
    <Notice tone="danger" role="alert">
      {discovery.actionError}
    </Notice>
  );
  const detail = discovery.detail;
  if (!detail) {
    return (
      <div className="space-y-4 p-5 sm:p-6">
        {actionError}
        <EmptyState
          icon={ListTodo}
          title="No requirements yet"
          action={
            <Button onClick={discovery.start} loading={discovery.busy}>
              Start requirements discovery
            </Button>
          }
        >
          The Requirements Analyst reads your brief and notes, asks up to five focused questions at a time, and keeps a
          versioned list of requirements for you to approve. Planning starts from the version you approve.
        </EmptyState>
      </div>
    );
  }

  const state = detail.session.state;
  const meta = SESSION_STATE_META[state];
  const terminal = isTerminalSessionState(state);
  const analysing = isAnalysing(detail);
  const turn = detail.turn;
  const version = detail.version;
  const streamLabel = STREAM_LABELS[discovery.stream];

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-5 sm:p-6">
      <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={meta.tone} dot>
              {meta.label}
            </Badge>
            {version && <span className="font-mono text-xs text-faint">requirements v{version.version}</span>}
            {turn && (
              <span className="text-xs text-faint">
                turn {turn.number} of up to {detail.maxTurns}
              </span>
            )}
          </div>
          <p className="mt-1.5 text-[0.8125rem] text-muted">{meta.description}</p>
          {streamLabel && (
            <p role="status" className="mt-1 text-xs text-faint">
              {streamLabel}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {!terminal && (
            <Button size="sm" variant="secondary" onClick={discovery.cancel} loading={discovery.busy}>
              Cancel session
            </Button>
          )}
          {terminal && (
            <Button size="sm" variant={state === 'approved' ? 'secondary' : 'primary'} onClick={discovery.start} loading={discovery.busy}>
              Start a new session
            </Button>
          )}
        </div>
      </div>

      {actionError}

      {analysing && (
        <div role="status" className="flex items-center gap-2 text-sm text-muted">
          <Spinner />
          {turn?.status === 'queued'
            ? `Turn ${turn.number} is waiting for a worker…`
            : `The Requirements Analyst is working on turn ${turn?.number ?? ''}…`}
        </div>
      )}

      {turn?.status === 'failed' && !terminal && (
        <Notice tone="danger" title={`Turn ${turn.number} failed`}>
          <p>{turn.failureMessage ?? 'The analyst turn failed.'} Your answers are kept.</p>
          <Button size="sm" className="mt-2" onClick={discovery.retryTurn} loading={discovery.busy}>
            Retry turn
          </Button>
        </Notice>
      )}

      {state === 'approved' && version && (
        <Notice tone="success" title={`Requirements v${version.version} approved`}>
          <p>
            Version {version.version} is immutable (sha256 <span className="font-mono">{version.contentSha256.slice(0, 12)}</span>…). The
            Project Manager plans from this exact version, covering every must-have or flagging it with a reason.
          </p>
          <Button size="sm" className="mt-2" onClick={onOpenPlan}>
            Plan from these requirements
          </Button>
        </Notice>
      )}

      {version && !version.content.readiness.ready && version.content.readiness.blockers.length > 0 && !terminal && (
        <Section title="Outstanding blockers">
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
            {version.content.readiness.blockers.map((blocker) => (
              <li key={blocker}>{blocker}</li>
            ))}
          </ul>
        </Section>
      )}

      {state === 'ready-for-review' && version && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface p-4">
          <p className="flex-1 text-sm text-muted">
            Submitting freezes v{version.version} for your approval. You can still ask more questions instead.
          </p>
          <Button size="sm" onClick={discovery.submitForApproval} loading={discovery.busy}>
            Submit v{version.version} for approval
          </Button>
        </div>
      )}

      <ApprovalControls discovery={discovery} detail={detail} />
      <Questions key={answersSignature(detail)} discovery={discovery} detail={detail} />
      {version && <RequirementsDocumentView version={version} />}
      {version && <VersionHistory key={version.version} sessionId={detail.session.id} />}
    </div>
  );
}
