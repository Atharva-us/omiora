import { AppError } from '@/domain/errors';
import type { RequirementsService } from '../contracts/requirements-service';

export const DISCOVERY_UNAVAILABLE_MESSAGE =
  'Requirements discovery needs API mode and a running Omniora backend. This build is in demo mode, so the Requirements Analyst cannot run.';

/** Demo mode: there is no backend, so discovery is unavailable. Nothing is simulated. */
export function createUnavailableRequirementsService(): RequirementsService {
  const reject = async (): Promise<never> => {
    throw new AppError('provider-not-configured', DISCOVERY_UNAVAILABLE_MESSAGE);
  };
  return {
    available: false,
    listSessions: async () => [],
    getSession: reject,
    startSession: reject,
    submitAnswers: reject,
    retryTurn: reject,
    submitForApproval: reject,
    decide: reject,
    cancel: reject,
    listVersions: async () => [],
    getVersion: reject,
    getApproved: async () => null,
  };
}
