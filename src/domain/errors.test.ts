import { describe, expect, it } from 'vitest';
import { AppError, GENERIC_ERROR_MESSAGE, isAppError, toUserMessage } from './errors';

describe('AppError and toUserMessage', () => {
  it('shows AppError messages, including user-safe details', () => {
    expect(toUserMessage(new AppError('not-found', 'This project no longer exists.'))).toBe(
      'This project no longer exists.',
    );
    expect(toUserMessage(new AppError('validation', 'Invalid.', { details: ['Name is required.'] }))).toBe(
      'Invalid. Name is required.',
    );
  });

  it('never shows messages from unknown errors', () => {
    expect(toUserMessage(new TypeError("Cannot read properties of undefined (reading 'x')"))).toBe(GENERIC_ERROR_MESSAGE);
    expect(toUserMessage('raw string')).toBe(GENERIC_ERROR_MESSAGE);
    expect(toUserMessage(undefined, 'Custom fallback')).toBe('Custom fallback');
  });

  it('keeps the cause for diagnostics without exposing it', () => {
    const cause = new Error('QuotaExceededError: secret internals');
    const error = new AppError('storage-unavailable', 'Storage is full.', { cause });
    expect(error.cause).toBe(cause);
    expect(isAppError(error)).toBe(true);
    expect(toUserMessage(error)).not.toContain('secret internals');
  });
});
