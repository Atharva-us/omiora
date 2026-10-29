/**
 * The single error type that crosses service boundaries.
 *
 * `message` must always be safe to show to a user: no stack traces, no raw
 * server output, no secrets. Diagnostic detail belongs in `cause` (logged,
 * never rendered) or `details` (user-safe validation messages).
 */
export const APP_ERROR_CODES = [
  'validation',
  'not-found',
  'read-only',
  'storage-unavailable',
  'provider-not-configured',
  'invalid-credentials',
  'email-in-use',
  'unauthenticated',
  'forbidden',
  'conflict',
  'rate-limited',
  'network',
  'configuration',
  'unexpected',
] as const;

export type AppErrorCode = (typeof APP_ERROR_CODES)[number];

interface AppErrorOptions {
  cause?: unknown;
  /** User-safe specifics, e.g. individual validation messages. */
  details?: readonly string[];
}

export class AppError extends Error {
  readonly code: AppErrorCode;
  readonly details: readonly string[];

  constructor(code: AppErrorCode, message: string, options: AppErrorOptions = {}) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause });
    this.name = 'AppError';
    this.code = code;
    this.details = options.details ?? [];
  }
}

export function isAppError(error: unknown): error is AppError {
  return error instanceof AppError;
}

export const GENERIC_ERROR_MESSAGE = 'Something went wrong. Please try again.';

/**
 * Returns text that is safe to render for any thrown value. Only `AppError`
 * messages are trusted; anything else (a TypeError, a raw network failure)
 * is replaced with a generic message and should be logged by the caller.
 */
export function toUserMessage(error: unknown, fallback: string = GENERIC_ERROR_MESSAGE): string {
  if (!isAppError(error)) return fallback;
  return error.details.length > 0 ? `${error.message} ${error.details.join(' ')}` : error.message;
}
