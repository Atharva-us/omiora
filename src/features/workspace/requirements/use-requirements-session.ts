import { useCallback, useEffect, useRef, useState } from 'react';
import type { AppErrorCode } from '@/domain/errors';
import {
  isTerminalSessionState,
  pendingRequirementsApproval,
  type AnswerInput,
  type RequirementsDecision,
  type SessionDetail,
} from '@/domain/requirements/requirements';
import { useAsyncData } from '@/hooks/use-async-data';
import { useErrorReporter } from '@/hooks/use-error-reporter';
import { useServices } from '@/hooks/use-services';
import type { RunStreamStatus } from '@/services/contracts/run-service';
import { newSubmissionKey } from './requirements-model';

export interface RequirementsSessionState {
  /** False in demo mode or for sample projects: the UI explains instead of offering actions. */
  available: boolean;
  detail: SessionDetail | null;
  stream: RunStreamStatus | 'idle';
  isLoading: boolean;
  loadError: { message: string; code: AppErrorCode | undefined } | null;
  actionError: string | null;
  busy: boolean;
  start: () => Promise<void>;
  saveAnswers: (answers: AnswerInput[], advance: boolean) => Promise<boolean>;
  retryTurn: () => Promise<void>;
  submitForApproval: () => Promise<void>;
  decide: (decision: RequirementsDecision, comment?: string) => Promise<void>;
  cancel: () => Promise<void>;
  reload: () => void;
}

/**
 * The latest discovery session for a project. Its events arrive on the shared run stream (a
 * session id is a run id); every event or reconnect re-fetches the session, because the API, not
 * the stream, is the source of truth. A refresh therefore resumes exactly where the server is.
 */
export function useRequirementsSession(projectId: string, enabled: boolean): RequirementsSessionState {
  const { requirements, runs } = useServices();
  const reportError = useErrorReporter();
  const available = requirements.available && enabled;

  const load = useCallback(async () => {
    if (!available) return null;
    const [latest] = await requirements.listSessions(projectId);
    return latest ? requirements.getSession(latest.id) : null;
  }, [available, requirements, projectId]);
  const { data, errorMessage, errorCode, isLoading, reload } = useAsyncData(load, 'requirements.load-failed');

  const [stream, setStream] = useState<RunStreamStatus | 'idle'>('idle');
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pendingStart = useRef<string | null>(null);
  const pendingAnswers = useRef<{ signature: string; key: string } | null>(null);
  const refreshTimer = useRef<number | undefined>(undefined);

  const detail = data ?? null;
  const sessionId = detail?.session.id;
  const terminal = detail ? isTerminalSessionState(detail.session.state) : true;
  const lastSeq = detail?.session.lastEventSeq ?? 0;
  const resumeFrom = useRef(lastSeq);
  useEffect(() => {
    resumeFrom.current = lastSeq;
  }, [lastSeq]);

  useEffect(() => {
    if (!sessionId || terminal) return;
    const scheduleRefresh = () => {
      window.clearTimeout(refreshTimer.current);
      refreshTimer.current = window.setTimeout(reload, 200);
    };
    const unsubscribe = runs.subscribe(sessionId, resumeFrom.current, {
      onEvent: scheduleRefresh,
      onStatus: (status) => {
        setStream(status);
        if (status === 'open') scheduleRefresh();
      },
      onEnd: scheduleRefresh,
    });
    return () => {
      unsubscribe();
      window.clearTimeout(refreshTimer.current);
    };
  }, [sessionId, terminal, runs, reload]);

  const act = useCallback(
    async (event: string, action: () => Promise<unknown>): Promise<boolean> => {
      setBusy(true);
      setActionError(null);
      try {
        await action();
        reload();
        return true;
      } catch (error) {
        setActionError(reportError(event, error, 'The request could not be completed. Please try again.'));
        return false;
      } finally {
        setBusy(false);
      }
    },
    [reload, reportError],
  );

  return {
    available,
    detail,
    stream: terminal ? 'idle' : stream,
    isLoading: available && isLoading && !data,
    loadError: errorMessage ? { message: errorMessage, code: errorCode } : null,
    actionError,
    busy,
    start: async () => {
      await act('requirements.start-failed', async () => {
        pendingStart.current ??= newSubmissionKey('discovery');
        await requirements.startSession(projectId, pendingStart.current);
        pendingStart.current = null;
      });
    },
    saveAnswers: (answers, advance) =>
      act('requirements.answers-failed', async () => {
        if (!sessionId) return;
        // The same submission retried after a failure reuses its key, so the server applies it once.
        const signature = JSON.stringify({ answers, advance });
        if (pendingAnswers.current?.signature !== signature) {
          pendingAnswers.current = { signature, key: newSubmissionKey('answers') };
        }
        await requirements.submitAnswers(sessionId, pendingAnswers.current.key, answers, advance);
        pendingAnswers.current = null;
      }),
    retryTurn: async () => {
      await act('requirements.retry-failed', () => (sessionId ? requirements.retryTurn(sessionId) : Promise.resolve()));
    },
    submitForApproval: async () => {
      await act('requirements.submit-failed', async () => {
        if (sessionId && detail?.version) await requirements.submitForApproval(sessionId, detail.version.version);
      });
    },
    decide: async (decision, comment) => {
      await act('requirements.decision-failed', async () => {
        const approval = detail ? pendingRequirementsApproval(detail) : null;
        if (!sessionId || !approval) return;
        await requirements.decide(sessionId, approval.id, {
          decision,
          version: approval.version,
          ...(comment ? { comment } : {}),
        });
      });
    },
    cancel: async () => {
      await act('requirements.cancel-failed', () => (sessionId ? requirements.cancel(sessionId) : Promise.resolve()));
    },
    reload,
  };
}
