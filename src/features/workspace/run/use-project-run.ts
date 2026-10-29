import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { AppErrorCode } from '@/domain/errors';
import { isTerminalRunState, type ApprovalDecision, type RunDetail, type RunEvent } from '@/domain/runs/run';
import { useAsyncData } from '@/hooks/use-async-data';
import { useErrorReporter } from '@/hooks/use-error-reporter';
import { useServices } from '@/hooks/use-services';
import type { RunStreamStatus } from '@/services/contracts/run-service';
import { newIdempotencyKey } from './run-model';

export interface ProjectRun {
  /** False in demo mode or for sample projects: the UI explains instead of offering actions. */
  available: boolean;
  detail: RunDetail | null;
  events: RunEvent[];
  stream: RunStreamStatus | 'idle';
  isLoading: boolean;
  loadError: { message: string; code: AppErrorCode | undefined } | null;
  actionError: string | null;
  busy: boolean;
  start: () => Promise<void>;
  cancel: () => Promise<void>;
  decide: (decision: ApprovalDecision, comment?: string) => Promise<void>;
  reload: () => void;
}

const mergeEvents = (base: RunEvent[], extra: RunEvent[]) => {
  const bySeq = new Map(base.map((event) => [event.seq, event]));
  for (const event of extra) bySeq.set(event.seq, event);
  return [...bySeq.values()].sort((a, b) => a.seq - b.seq);
};

/**
 * The latest planning run for a project. Persisted events stream in over SSE; each event (and each
 * reconnect) triggers a re-fetch of the run, because the API, not the stream, is the source of truth.
 */
export function useProjectRun(projectId: string, enabled: boolean): ProjectRun {
  const { runs } = useServices();
  const reportError = useErrorReporter();
  const available = runs.available && enabled;

  const load = useCallback(async () => {
    if (!available) return null;
    const [latest] = await runs.listRuns(projectId);
    if (!latest) return null;
    const [detail, events] = await Promise.all([runs.getRun(latest.id), runs.listEvents(latest.id, 0)]);
    return { detail, events };
  }, [available, runs, projectId]);
  const { data, errorMessage, errorCode, isLoading, reload } = useAsyncData(load, 'run.load-failed');

  const [streamed, setStreamed] = useState<{ runId: string; events: RunEvent[] } | null>(null);
  const [stream, setStream] = useState<RunStreamStatus | 'idle'>('idle');
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pendingKey = useRef<string | null>(null);
  const refreshTimer = useRef<number | undefined>(undefined);

  const detail = data?.detail ?? null;
  const runId = detail?.run.id;
  const terminal = detail ? isTerminalRunState(detail.run.state) : true;
  const lastLoadedSeq = data?.events.at(-1)?.seq ?? 0;

  // Where a new subscription starts. Kept in a ref (updated after render) so reloads do not
  // tear down and reopen the stream; the browser's Last-Event-ID handles later reconnects.
  const resumeFrom = useRef(lastLoadedSeq);
  useEffect(() => {
    resumeFrom.current = lastLoadedSeq;
  }, [lastLoadedSeq]);

  // Subscribe while the run is active.
  useEffect(() => {
    if (!runId || terminal) return;
    const scheduleRefresh = () => {
      window.clearTimeout(refreshTimer.current);
      refreshTimer.current = window.setTimeout(reload, 200);
    };
    const unsubscribe = runs.subscribe(runId, resumeFrom.current, {
      onEvent: (event) => {
        setStreamed((previous) => ({
          runId,
          events: mergeEvents(previous?.runId === runId ? previous.events : [], [event]),
        }));
        scheduleRefresh();
      },
      onStatus: (status) => {
        setStream(status);
        if (status === 'open') scheduleRefresh(); // reconcile after (re)connecting
      },
      onEnd: scheduleRefresh,
    });
    return () => {
      unsubscribe();
      window.clearTimeout(refreshTimer.current);
    };
  }, [runId, terminal, runs, reload]);

  const events = useMemo(
    () => mergeEvents(data?.events ?? [], streamed && streamed.runId === runId ? streamed.events : []),
    [data, streamed, runId],
  );

  const act = useCallback(
    async (event: string, action: () => Promise<unknown>) => {
      setBusy(true);
      setActionError(null);
      try {
        await action();
        reload();
      } catch (error) {
        setActionError(reportError(event, error, 'The request could not be completed. Please try again.'));
      } finally {
        setBusy(false);
      }
    },
    [reload, reportError],
  );

  return {
    available,
    detail,
    events,
    stream: terminal ? 'idle' : stream,
    isLoading: available && isLoading && !data,
    loadError: errorMessage ? { message: errorMessage, code: errorCode } : null,
    actionError,
    busy,
    start: () =>
      act('run.start-failed', async () => {
        pendingKey.current ??= newIdempotencyKey();
        await runs.startPlanning(projectId, pendingKey.current);
        pendingKey.current = null;
      }),
    cancel: () => act('run.cancel-failed', () => (runId ? runs.cancel(runId) : Promise.resolve())),
    decide: (decision, comment) =>
      act('run.decision-failed', async () => {
        const approval = detail?.approvals.find(
          (candidate) => candidate.status === 'pending' && candidate.planVersion === detail.run.currentPlanVersion,
        );
        if (!detail || !approval) return;
        await runs.decide(detail.run.id, approval.id, {
          decision,
          planVersion: approval.planVersion,
          ...(comment ? { comment } : {}),
        });
      }),
    reload,
  };
}
