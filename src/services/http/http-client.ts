import { z } from 'zod/mini';
import { APP_ERROR_CODES, AppError, type AppErrorCode } from '@/domain/errors';

/**
 * Shared transport for the HTTP adapters.
 * - Sends the session cookie (`credentials: 'include'`) and the CSRF header the API requires.
 * - Maps error responses to `AppError` using the server's finite code set.
 * - Validates every success body with a schema, so malformed data never reaches the UI.
 */

export const CSRF_HEADER = { 'X-Omniora-Client': 'web' } as const;

const errorBodySchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.optional(z.array(z.string())),
  }),
});

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export interface RequestOptions<T> {
  body?: unknown;
  headers?: Record<string, string>;
  /** Omit for endpoints that return no content (204). */
  schema?: z.ZodMiniType<T>;
}

export interface HttpClient {
  readonly baseUrl: string;
  request<T>(method: 'GET' | 'POST' | 'PATCH' | 'DELETE', path: string, options?: RequestOptions<T>): Promise<T>;
}

const isAppErrorCode = (code: string): code is AppErrorCode => (APP_ERROR_CODES as readonly string[]).includes(code);

async function toAppError(response: Response): Promise<AppError> {
  let parsed: z.infer<typeof errorBodySchema> | null = null;
  try {
    const result = errorBodySchema.safeParse(await response.json());
    parsed = result.success ? result.data : null;
  } catch {
    // Not JSON (for example a proxy error page): fall through to a status-based message.
  }
  if (parsed && isAppErrorCode(parsed.error.code)) {
    // The API contract guarantees these messages are safe to show.
    return new AppError(parsed.error.code, parsed.error.message, { details: parsed.error.details ?? [] });
  }
  if (response.status >= 500) {
    return new AppError('network', 'The Omniora API is having problems. Try again shortly.');
  }
  return new AppError('unexpected', `The request failed (HTTP ${response.status}).`);
}

export function createHttpClient(baseUrl: string, fetchImpl: FetchLike = (input, init) => fetch(input, init)): HttpClient {
  return {
    baseUrl,
    async request<T>(method: string, path: string, options: RequestOptions<T> = {}): Promise<T> {
      const headers: Record<string, string> = { ...CSRF_HEADER, Accept: 'application/json', ...options.headers };
      if (options.body !== undefined) headers['Content-Type'] = 'application/json';
      let response: Response;
      try {
        response = await fetchImpl(`${baseUrl}${path}`, {
          method,
          credentials: 'include',
          headers,
          body: options.body === undefined ? undefined : JSON.stringify(options.body),
        });
      } catch (cause) {
        throw new AppError('network', `Cannot reach the Omniora API at ${baseUrl}. Check that the backend is running.`, {
          cause,
        });
      }
      if (!response.ok) throw await toAppError(response);
      if (!options.schema) return undefined as T;
      let json: unknown;
      try {
        json = await response.json();
      } catch (cause) {
        throw new AppError('unexpected', 'The server returned an unreadable response.', { cause });
      }
      const result = options.schema.safeParse(json);
      if (!result.success) {
        throw new AppError('unexpected', 'The server returned data this app does not understand.', { cause: result.error });
      }
      return result.data;
    },
  };
}
