import { afterEach, describe, expect, it, vi } from 'vitest';
import { AppError } from '@/domain/errors';
import { createBrowserStore, createMemoryStore } from './key-value-store';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('createBrowserStore', () => {
  it('round-trips JSON values', () => {
    const store = createBrowserStore('local');
    store.set('k', { a: [1, 2] });
    expect(store.get('k')).toEqual({ a: [1, 2] });
    store.remove('k');
    expect(store.get('k')).toBeUndefined();
  });

  it('treats corrupt JSON as missing', () => {
    window.sessionStorage.setItem('k', '{not json');
    expect(createBrowserStore('session').get('k')).toBeUndefined();
  });

  it('throws storage-unavailable when a write fails', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('quota', 'QuotaExceededError');
    });
    const attempt = () => createBrowserStore('local').set('k', 1);
    expect(attempt).toThrow(AppError);
    try {
      attempt();
    } catch (error) {
      expect(error).toMatchObject({ code: 'storage-unavailable' });
      expect((error as AppError).cause).toBeInstanceOf(DOMException);
    }
  });

  it('throws storage-unavailable when storage access itself is blocked', () => {
    vi.spyOn(window, 'localStorage', 'get').mockImplementation(() => {
      throw new DOMException('denied', 'SecurityError');
    });
    expect(() => createBrowserStore('local').get('k')).toThrow(/Browser storage is unavailable/);
  });
});

describe('createMemoryStore', () => {
  it('copies values like real storage does', () => {
    const value = { list: [1] };
    const store = createMemoryStore();
    store.set('k', value);
    value.list.push(2);
    expect(store.get('k')).toEqual({ list: [1] });
  });
});
