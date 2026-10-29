import { describe, expect, it, vi } from 'vitest';
import { AppError } from '@/domain/errors';
import { createConsoleLogger, redact } from './logger';

describe('redact', () => {
  it('removes sensitive values at any nesting level', () => {
    const result = redact({
      password: 'hunter2',
      request: { headers: { Authorization: 'Bearer abc', 'x-trace': 't1' }, apiKey: 'sk-123' },
      sessionToken: 'tok',
      email: 'dev@example.com',
    });
    expect(JSON.stringify(result)).not.toMatch(/hunter2|Bearer abc|sk-123|"tok"/);
    expect(result).toMatchObject({ email: 'dev@example.com', request: { headers: { 'x-trace': 't1' } } });
  });

  it('flattens errors, keeping codes and causes but omitting stacks unless asked', () => {
    const error = new AppError('storage-unavailable', 'Storage is full.', { cause: new Error('quota') });
    const flat = redact({ error }) as { error: Record<string, unknown> };
    expect(flat.error).toMatchObject({ name: 'AppError', code: 'storage-unavailable', cause: { message: 'quota' } });
    expect(flat.error).not.toHaveProperty('stack');
    expect((redact({ error }, true) as { error: Record<string, unknown> }).error).toHaveProperty('stack');
  });
});

describe('createConsoleLogger', () => {
  it('filters by level and prefixes events', () => {
    const sink = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };
    const logger = createConsoleLogger({ minLevel: 'warn', sink });
    logger.debug('a');
    logger.info('b');
    logger.warn('c', { token: 'secret' });
    logger.error('d');
    expect(sink.debug).not.toHaveBeenCalled();
    expect(sink.info).not.toHaveBeenCalled();
    expect(sink.warn).toHaveBeenCalledWith('[omniora] c', { token: '[redacted]' });
    expect(sink.error).toHaveBeenCalledWith('[omniora] d', {});
  });

  it('emits nothing when silent', () => {
    const sink = { debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn() };
    createConsoleLogger({ minLevel: 'silent', sink }).error('x');
    expect(sink.error).not.toHaveBeenCalled();
  });
});
