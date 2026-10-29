import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { AuthUser } from '@/domain/authentication/types';
import { useServices } from '@/hooks/use-services';
import { SessionContext, type SessionState } from '@/hooks/session-context';

/**
 * Who is signed in, as reported by the server (`GET /auth/me`). The browser holds only an
 * HttpOnly cookie, so the UI asks the API rather than reading any token.
 */
export function SessionProvider({ children }: { children: ReactNode }) {
  const { auth, logger } = useServices();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<SessionState['status']>(auth.isConfigured ? 'loading' : 'ready');

  const refresh = useCallback(async () => {
    if (!auth.isConfigured) return;
    try {
      setUser(await auth.getCurrentUser());
    } catch (error) {
      logger.warn('session.refresh-failed', { error });
      setUser(null);
    } finally {
      setStatus('ready');
    }
  }, [auth, logger]);

  useEffect(() => {
    if (!auth.isConfigured) return;
    let active = true;
    auth.getCurrentUser().then(
      (current) => {
        if (!active) return;
        setUser(current);
        setStatus('ready');
      },
      (error: unknown) => {
        if (!active) return;
        logger.warn('session.load-failed', { error });
        setStatus('ready');
      },
    );
    return () => {
      active = false;
    };
  }, [auth, logger]);

  const signOut = useCallback(async () => {
    try {
      await auth.signOut();
    } finally {
      setUser(null);
    }
  }, [auth]);

  const value = useMemo(() => ({ user, status, refresh, signOut }), [user, status, refresh, signOut]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
