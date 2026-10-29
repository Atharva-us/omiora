import { useCallback } from 'react';
import { isAppError, toUserMessage } from '@/domain/errors';
import { useServices } from './use-services';

/**
 * Converts a caught error into user-safe text. Expected failures (`AppError`
 * with a known code) are returned as-is; anything else is logged, because it
 * indicates a bug, and replaced with `fallback`.
 */
export function useErrorReporter() {
  const { logger } = useServices();
  return useCallback(
    (event: string, error: unknown, fallback?: string): string => {
      if (!isAppError(error) || error.code === 'unexpected') logger.error(event, { error });
      return toUserMessage(error, fallback);
    },
    [logger],
  );
}
