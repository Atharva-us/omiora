/**
 * Minimal structured logging port. Events are dot-separated identifiers
 * (`storage.write-failed`); context is a flat object. A remote sink can
 * implement the same interface later without touching call sites.
 */
export const LOG_LEVELS = ['debug', 'info', 'warn', 'error', 'silent'] as const;
export type LogLevel = (typeof LOG_LEVELS)[number];
export type LogContext = Record<string, unknown>;

export interface Logger {
  debug(event: string, context?: LogContext): void;
  info(event: string, context?: LogContext): void;
  warn(event: string, context?: LogContext): void;
  error(event: string, context?: LogContext): void;
}

const SENSITIVE_KEY = /pass(word)?|secret|token|authorization|cookie|api[-_]?key|credential|session/i;
const REDACTED = '[redacted]';

function serializeError(error: Error, includeStack: boolean): LogContext {
  const code = 'code' in error ? error.code : undefined;
  return {
    name: error.name,
    message: error.message,
    ...(typeof code === 'string' ? { code } : {}),
    ...(includeStack && error.stack ? { stack: error.stack } : {}),
    ...(error.cause instanceof Error ? { cause: serializeError(error.cause, includeStack) } : {}),
  };
}

/** Removes values under sensitive-looking keys and flattens errors. Recurses into plain objects only. */
export function redact(context: LogContext, includeStack = false, depth = 0): LogContext {
  const result: LogContext = {};
  for (const [key, value] of Object.entries(context)) {
    if (SENSITIVE_KEY.test(key)) result[key] = REDACTED;
    else if (value instanceof Error) result[key] = serializeError(value, includeStack);
    else if (value && typeof value === 'object' && !Array.isArray(value) && depth < 3)
      result[key] = redact(value as LogContext, includeStack, depth + 1);
    else result[key] = value;
  }
  return result;
}

type Sink = Pick<Console, 'debug' | 'info' | 'warn' | 'error'>;

interface ConsoleLoggerOptions {
  minLevel: LogLevel;
  /** Include stack traces (development only). */
  includeStacks?: boolean;
  sink?: Sink;
}

export function createConsoleLogger({ minLevel, includeStacks = false, sink = console }: ConsoleLoggerOptions): Logger {
  const threshold = LOG_LEVELS.indexOf(minLevel);
  const emit = (level: Exclude<LogLevel, 'silent'>) => (event: string, context: LogContext = {}) => {
    if (LOG_LEVELS.indexOf(level) < threshold) return;
    sink[level](`[omniora] ${event}`, redact(context, includeStacks));
  };
  return { debug: emit('debug'), info: emit('info'), warn: emit('warn'), error: emit('error') };
}

export interface RecordedLogEntry {
  level: Exclude<LogLevel, 'silent'>;
  event: string;
  context: LogContext;
}

/** Captures entries in memory (after redaction) for tests. */
export function createMemoryLogger(): Logger & { entries: RecordedLogEntry[] } {
  const entries: RecordedLogEntry[] = [];
  const record = (level: RecordedLogEntry['level']) => (event: string, context: LogContext = {}) => {
    entries.push({ level, event, context: redact(context) });
  };
  return { entries, debug: record('debug'), info: record('info'), warn: record('warn'), error: record('error') };
}
