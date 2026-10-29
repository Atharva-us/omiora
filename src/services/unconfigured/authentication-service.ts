import { AppError } from '@/domain/errors';
import type { AuthenticationService } from '../contracts/authentication-service';

const NOT_CONFIGURED_MESSAGE =
  'Accounts are not available yet. No authentication provider is connected to this build of Omniora.';

/**
 * Used until an identity provider exists. It never pretends to
 * authenticate: every credential-bearing call rejects with
 * `provider-not-configured`, and no credentials are stored or transmitted.
 */
export function createUnconfiguredAuthService(): AuthenticationService {
  const reject = async (): Promise<never> => {
    throw new AppError('provider-not-configured', NOT_CONFIGURED_MESSAGE);
  };
  return {
    isConfigured: false,
    getCurrentUser: async () => null,
    signIn: reject,
    register: reject,
    requestPasswordReset: reject,
    signOut: async () => {},
  };
}
