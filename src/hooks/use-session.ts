import { useContext } from 'react';
import { SessionContext, type SessionState } from './session-context';

export function useSession(): SessionState {
  const session = useContext(SessionContext);
  if (!session) throw new Error('useSession must be used inside <SessionProvider>.');
  return session;
}
