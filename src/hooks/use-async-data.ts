import { useCallback, useEffect, useState } from 'react';
import { isAppError, type AppErrorCode } from '@/domain/errors';
import { useErrorReporter } from './use-error-reporter';

interface Settled<T> {
  loader: () => Promise<T>;
  nonce: number;
  data?: T;
  error?: { message: string; code: AppErrorCode };
}

export interface AsyncData<T> {
  /** Most recent successful result; kept while a reload is in flight. */
  data: T | undefined;
  /** User-safe description of the last failure. Raw errors are logged, never exposed. */
  errorMessage: string | undefined;
  /** Lets views offer the right recovery, e.g. "Sign in" for `unauthenticated`. */
  errorCode: AppErrorCode | undefined;
  isLoading: boolean;
  reload: () => void;
}

/**
 * Runs `loader` and tracks its result. Pass a stable (memoised) loader;
 * a new loader identity triggers a fresh load. `event` names the failure
 * in logs, e.g. `projects.load-failed`.
 */
export function useAsyncData<T>(loader: () => Promise<T>, event: string): AsyncData<T> {
  const reportError = useErrorReporter();
  const [nonce, setNonce] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const [lastData, setLastData] = useState<{ loader: () => Promise<T>; data: T } | null>(null);

  useEffect(() => {
    let active = true;
    loader().then(
      (data) => {
        if (!active) return;
        setSettled({ loader, nonce, data });
        setLastData({ loader, data });
      },
      (error: unknown) => {
        if (!active) return;
        const code: AppErrorCode = isAppError(error) ? error.code : 'unexpected';
        setSettled({ loader, nonce, error: { message: reportError(event, error), code } });
      },
    );
    return () => {
      active = false;
    };
  }, [loader, nonce, event, reportError]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);
  const current = settled && settled.loader === loader && settled.nonce === nonce ? settled : null;

  return {
    data: current?.data ?? (lastData?.loader === loader ? lastData.data : undefined),
    errorMessage: current?.error?.message,
    errorCode: current?.error?.code,
    isLoading: current === null,
    reload,
  };
}
