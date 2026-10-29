import { describe, expect, it, vi } from 'vitest';
import { z } from 'zod/mini';
import { AppError } from '@/domain/errors';
import type { RunStreamStatus } from '@/services/contracts/run-service';
import { createHttpAuthService } from './authentication-service';
import { createHttpClient } from './http-client';
import { createHttpProjectService } from './project-service';
import { createHttpRequirementsService } from './requirements-service';
import { createHttpRunService, type EventSourceLike } from './run-service';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const catchError = async (promise: Promise<unknown>) => promise.then(() => null, (error: unknown) => error as AppError);

describe('http client', () => {
  const schema = z.object({ ok: z.boolean() });

  it('maps API error bodies to AppError with the server message and details', async () => {
    const http = createHttpClient('https://api.test', async () =>
      json({ error: { code: 'validation', message: 'The project configuration is not valid.', details: ['Name required.'] } }, 422),
    );
    const error = await catchError(http.request('GET', '/x', { schema }));
    expect(error).toBeInstanceOf(AppError);
    expect(error).toMatchObject({ code: 'validation', message: 'The project configuration is not valid.' });
    expect(error?.details).toEqual(['Name required.']);
  });

  it('never trusts unknown codes or non-JSON bodies', async () => {
    const unknown = createHttpClient('https://api.test', async () => json({ error: { code: 'teapot', message: '<script>' } }, 418));
    expect(await catchError(unknown.request('GET', '/x', { schema }))).toMatchObject({ code: 'unexpected' });
    const proxy = createHttpClient('https://api.test', async () => new Response('<html>Bad gateway</html>', { status: 502 }));
    expect(await catchError(proxy.request('GET', '/x', { schema }))).toMatchObject({ code: 'network' });
  });

  it('reports an unreachable API as a network error', async () => {
    const http = createHttpClient('https://api.test', async () => {
      throw new TypeError('Failed to fetch');
    });
    const error = await catchError(http.request('GET', '/x', { schema }));
    expect(error).toMatchObject({ code: 'network' });
    expect(error?.message).toContain('https://api.test');
  });

  it('rejects success bodies that do not match the schema', async () => {
    const http = createHttpClient('https://api.test', async () => json({ ok: 'yes' }));
    expect(await catchError(http.request('GET', '/x', { schema }))).toMatchObject({ code: 'unexpected' });
  });
});

describe('http project and auth services', () => {
  const project = {
    id: '0192f6a0-0000-7000-8000-000000000001',
    source: 'user',
    status: 'configured',
    createdAt: '2026-10-29T12:00:00.000Z',
    updatedAt: '2026-10-29T12:00:00.000Z',
    configuration: {
      name: 'Shop',
      description: 'A storefront for handmade goods',
      platform: 'website',
      referenceUrl: '',
      stack: { mode: 'recommend' },
      requirements: { features: [], custom: '' },
    },
  };

  it('follows pagination cursors until exhausted', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json({ items: [project], nextCursor: 'abc' }))
      .mockResolvedValueOnce(json({ items: [{ ...project, id: '0192f6a0-0000-7000-8000-000000000002' }], nextCursor: null }));
    const service = createHttpProjectService(createHttpClient('https://api.test', fetch));
    expect(await service.listProjects()).toHaveLength(2);
    expect(fetch.mock.calls[1]?.[0]).toBe('https://api.test/api/v1/projects?limit=100&cursor=abc');
  });

  it('maps not-found to null and unauthenticated to a signed-out user', async () => {
    const notFound = createHttpProjectService(
      createHttpClient('https://api.test', async () => json({ error: { code: 'not-found', message: 'Gone.' } }, 404)),
    );
    expect(await notFound.getProject('missing')).toBeNull();
    const auth = createHttpAuthService(
      createHttpClient('https://api.test', async () => json({ error: { code: 'unauthenticated', message: 'Sign in.' } }, 401)),
    );
    expect(await auth.getCurrentUser()).toBeNull();
  });
});

class FakeEventSource implements EventSourceLike {
  readyState = 0;
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closed = false;
  private listeners = new Map<string, ((event: MessageEvent<string>) => void)[]>();
  readonly url: string;
  constructor(url: string) {
    this.url = url;
  }
  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }
  emit(type: string, data: unknown) {
    for (const listener of this.listeners.get(type) ?? []) listener({ data: JSON.stringify(data) } as MessageEvent<string>);
  }
  close() {
    this.closed = true;
    this.readyState = 2;
  }
}

describe('http run service', () => {
  it('starts planning with the idempotency key header', async () => {
    const fetch = vi.fn(async () =>
      json({
        id: 'r1', projectId: 'p1', agentRole: 'project-manager', state: 'queued', currentPlanVersion: null,
        failureCode: null, failureMessage: null, lastEventSeq: 1, pinnedRequirementsVersionId: null, requirementsSkipped: false,
        createdAt: '2026-10-29T12:00:00.000Z', updatedAt: '2026-10-29T12:00:00.000Z',
      }, 202),
    );
    const runs = createHttpRunService(createHttpClient('https://api.test', fetch));
    expect((await runs.startPlanning('p1', 'start-abc12345')).state).toBe('queued');
    expect(fetch).toHaveBeenCalledWith(
      'https://api.test/api/v1/projects/p1/runs',
      expect.objectContaining({ method: 'POST', headers: expect.objectContaining({ 'Idempotency-Key': 'start-abc12345' }) }),
    );
  });

  it('streams validated events, reports connection state, and closes on end', () => {
    let source!: FakeEventSource;
    const runs = createHttpRunService(createHttpClient('https://api.test'), (url) => (source = new FakeEventSource(url)));
    const events: number[] = [];
    const statuses: RunStreamStatus[] = [];
    const ended: string[] = [];
    runs.subscribe('r1', 4, {
      onEvent: (event) => events.push(event.seq),
      onStatus: (status) => statuses.push(status),
      onEnd: (state) => ended.push(state),
    });
    expect(source.url).toBe('https://api.test/api/v1/runs/r1/events?after=4');
    source.onopen?.(new Event('open'));
    source.emit('plan.created', { seq: 5, type: 'plan.created', data: { plan_version: 1 }, at: '2026-10-29T12:00:00.000Z' });
    source.emit('plan.created', { seq: 'bad' }); // malformed frames are ignored
    source.onerror?.(new Event('error'));
    source.emit('end', { state: 'approved' });
    expect(events).toEqual([5]);
    expect(statuses).toEqual(['connecting', 'open', 'reconnecting', 'closed']);
    expect(ended).toEqual(['approved']);
    expect(source.closed).toBe(true);
  });
});

describe('http requirements service', () => {
  it('posts answers with the idempotency key and maps a missing approval to null', async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    const fetch = vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith('/requirements/approved')) {
        return json({ error: { code: 'not-found', message: 'This project has no approved requirements yet.' } }, 404);
      }
      return json({ error: { code: 'conflict', message: 'The analyst is still working on the previous turn.' } }, 409);
    });
    const service = createHttpRequirementsService(createHttpClient('https://api.test', fetch));
    expect(await service.getApproved('p1')).toBeNull();
    const error = await catchError(
      service.submitAnswers('s1', 'answers-abc', [{ questionKey: 'DQ-001', unknown: true }], true),
    );
    expect(error).toMatchObject({ code: 'conflict' });
    const post = calls[1]!;
    expect(post.url).toBe('https://api.test/api/v1/requirements-sessions/s1/answers');
    expect(post.init?.headers).toMatchObject({ 'Idempotency-Key': 'answers-abc', 'X-Omniora-Client': 'web' });
    expect(JSON.parse(String(post.init?.body))).toEqual({ answers: [{ questionKey: 'DQ-001', unknown: true }], advance: true });
  });

  it('requests a version diff and rejects malformed session data', async () => {
    const fetch = vi.fn(async () => json({ session: { id: 's1' } }));
    const service = createHttpRequirementsService(createHttpClient('https://api.test', fetch));
    expect(await catchError(service.getSession('s1'))).toMatchObject({ code: 'unexpected' });
    await catchError(service.getVersion('s1', 3, 2));
    expect(fetch).toHaveBeenLastCalledWith('https://api.test/api/v1/requirements-sessions/s1/versions/3?diff=2', expect.anything());
  });
});
