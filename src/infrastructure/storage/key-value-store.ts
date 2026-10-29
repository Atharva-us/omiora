import { AppError } from '@/domain/errors';

/**
 * Port for JSON key-value persistence.
 *
 * - `get` returns `undefined` for missing or unparseable entries. Callers
 *   must validate the returned value (it is untrusted) with a schema.
 * - `set` and `remove` throw `AppError('storage-unavailable')` when the
 *   write did not happen (quota exceeded, storage blocked). Callers decide
 *   whether that is fatal (project data) or best-effort (UI drafts).
 *
 * Never store passwords, tokens, or API keys through this interface.
 */
export interface KeyValueStore {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
  remove(key: string): void;
}

const UNAVAILABLE_MESSAGE =
  'Browser storage is unavailable or full, so changes could not be saved. Check that site data is allowed for this page.';

function unavailable(cause: unknown): AppError {
  return new AppError('storage-unavailable', UNAVAILABLE_MESSAGE, { cause });
}

function parse(raw: string | null): unknown {
  if (raw === null) return undefined;
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    // Corrupt JSON is treated like a missing entry; schema validation follows anyway.
    return undefined;
  }
}

export function createBrowserStore(kind: 'local' | 'session'): KeyValueStore {
  const storage = (): Storage => {
    try {
      return kind === 'local' ? window.localStorage : window.sessionStorage;
    } catch (error) {
      // Accessing the property itself throws when site data is blocked.
      throw unavailable(error);
    }
  };
  return {
    get(key) {
      const store = storage();
      try {
        return parse(store.getItem(key));
      } catch (error) {
        throw unavailable(error);
      }
    },
    set(key, value) {
      const store = storage();
      try {
        store.setItem(key, JSON.stringify(value));
      } catch (error) {
        throw unavailable(error);
      }
    },
    remove(key) {
      const store = storage();
      try {
        store.removeItem(key);
      } catch (error) {
        throw unavailable(error);
      }
    },
  };
}

/** In-memory implementation for tests and non-persistent contexts. Round-trips through JSON like real storage. */
export function createMemoryStore(initial: Record<string, unknown> = {}): KeyValueStore {
  const entries = new Map(Object.entries(initial).map(([key, value]) => [key, JSON.stringify(value)]));
  return {
    get: (key) => parse(entries.get(key) ?? null),
    set: (key, value) => {
      entries.set(key, JSON.stringify(value));
    },
    remove: (key) => {
      entries.delete(key);
    },
  };
}
