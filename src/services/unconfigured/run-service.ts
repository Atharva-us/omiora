import { AppError } from '@/domain/errors';
import type { RunService } from '../contracts/run-service';

export const RUNS_UNAVAILABLE_MESSAGE =
  'Planning runs need API mode and a running Omniora backend. This build is in demo mode, so no agent can run.';

/** Demo mode: there is no backend, so runs are unavailable. Nothing is simulated. */
export function createUnavailableRunService(): RunService {
  const reject = async (): Promise<never> => {
    throw new AppError('provider-not-configured', RUNS_UNAVAILABLE_MESSAGE);
  };
  return {
    available: false,
    listRuns: async () => [],
    getRun: reject,
    startPlanning: reject,
    cancel: reject,
    decide: reject,
    listEvents: async () => [],
    subscribe: () => () => {},
  };
}
