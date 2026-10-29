import { createContext } from 'react';
import type { AuthUser } from '@/domain/authentication/types';

export interface SessionState {
  /** `null` when signed out, or always in demo mode (no identity provider). */
  user: AuthUser | null;
  status: 'loading' | 'ready';
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

export const SessionContext = createContext<SessionState | null>(null);
