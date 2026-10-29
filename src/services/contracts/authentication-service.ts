import type { AuthUser, Credentials, RegistrationInput } from '@/domain/authentication/types';

/**
 * Integration boundary for authentication.
 *
 * Implementations must keep tokens out of JavaScript-readable storage:
 * use HttpOnly, Secure, SameSite cookies issued by the backend or a hosted
 * identity provider. The UI only ever sees `AuthUser`. Failures are thrown
 * as `AppError` with codes `invalid-credentials`, `email-in-use`,
 * `network`, or `provider-not-configured`.
 */
export interface AuthenticationService {
  /** Whether a real identity provider is wired up. */
  readonly isConfigured: boolean;
  getCurrentUser(): Promise<AuthUser | null>;
  signIn(credentials: Credentials): Promise<AuthUser>;
  register(input: RegistrationInput): Promise<AuthUser>;
  /** Must resolve identically whether or not the account exists. */
  requestPasswordReset(email: string): Promise<void>;
  signOut(): Promise<void>;
}
