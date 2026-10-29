import { z } from 'zod/mini';
import { isAppError } from '@/domain/errors';
import type { AuthenticationService } from '../contracts/authentication-service';
import type { HttpClient } from './http-client';

const userSchema = z.object({ id: z.string(), email: z.string(), name: z.string() });

/**
 * Server-side sessions: the API sets an HttpOnly cookie on sign-in. This
 * adapter never sees or stores a token; it only receives the user profile.
 */
export function createHttpAuthService(http: HttpClient): AuthenticationService {
  return {
    isConfigured: true,
    async getCurrentUser() {
      try {
        return await http.request('GET', '/api/v1/auth/me', { schema: userSchema });
      } catch (error) {
        if (isAppError(error) && error.code === 'unauthenticated') return null;
        throw error;
      }
    },
    signIn: (credentials) => http.request('POST', '/api/v1/auth/sign-in', { body: credentials, schema: userSchema }),
    register: (input) => http.request('POST', '/api/v1/auth/register', { body: input, schema: userSchema }),
    requestPasswordReset: (email) => http.request('POST', '/api/v1/auth/password-reset', { body: { email } }),
    signOut: () => http.request('POST', '/api/v1/auth/sign-out'),
  };
}
