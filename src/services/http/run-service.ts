import { z } from 'zod/mini';
import {
  approvalSchema,
  RUN_EVENT_TYPES,
  runDetailSchema,
  runEventSchema,
  runSchema,
  runStateSchema,
} from '@/domain/runs/run';
import type { RunService, RunStreamHandlers } from '../contracts/run-service';
import type { HttpClient } from './http-client';

/** The subset of the browser EventSource API this adapter uses (injectable for tests). */
export interface EventSourceLike {
  readonly readyState: number;
  addEventListener(type: string, listener: (event: MessageEvent<string>) => void): void;
  onopen: ((event: Event) => void) | null;
  onerror: ((event: Event) => void) | null;
  close(): void;
}

export type EventSourceFactory = (url: string) => EventSourceLike;

const CLOSED = 2;
const endSchema = z.object({ state: runStateSchema });

const defaultEventSource: EventSourceFactory = (url) => new EventSource(url, { withCredentials: true });

/** RunService over the FastAPI backend (docs/BACKEND_CONTRACTS.md §5). */
export function createHttpRunService(http: HttpClient, createEventSource: EventSourceFactory = defaultEventSource): RunService {
  const runPath = (id: string) => `/api/v1/runs/${encodeURIComponent(id)}`;
  return {
    available: true,
    listRuns: (projectId) =>
      http.request('GET', `/api/v1/projects/${encodeURIComponent(projectId)}/runs`, { schema: z.array(runSchema) }),
    getRun: (runId) => http.request('GET', runPath(runId), { schema: runDetailSchema }),
    startPlanning: (projectId, idempotencyKey, options) =>
      http.request('POST', `/api/v1/projects/${encodeURIComponent(projectId)}/runs`, {
        headers: { 'Idempotency-Key': idempotencyKey },
        ...(options?.withoutRequirements ? { body: { withoutRequirements: true } } : {}),
        schema: runSchema,
      }),
    cancel: (runId) => http.request('POST', `${runPath(runId)}/cancel`, { schema: runSchema }),
    decide: (runId, approvalId, input) =>
      http.request('POST', `${runPath(runId)}/approvals/${encodeURIComponent(approvalId)}`, {
        body: input,
        schema: approvalSchema,
      }),
    listEvents: (runId, afterSeq) =>
      http.request('GET', `${runPath(runId)}/events/history?after=${afterSeq}`, { schema: z.array(runEventSchema) }),

    subscribe(runId, afterSeq, handlers: RunStreamHandlers) {
      // The browser tracks the last event id and sends it as Last-Event-ID when it reconnects,
      // so `after` only applies to the first connection.
      const source = createEventSource(`${http.baseUrl}${runPath(runId)}/events?after=${afterSeq}`);
      let closed = false;
      handlers.onStatus('connecting');
      source.onopen = () => handlers.onStatus('open');
      source.onerror = () => {
        if (closed) return;
        handlers.onStatus(source.readyState === CLOSED ? 'closed' : 'reconnecting');
      };
      for (const type of RUN_EVENT_TYPES) {
        source.addEventListener(type, (message) => {
          let data: unknown;
          try {
            data = JSON.parse(message.data);
          } catch {
            return; // ignore malformed frames; getRun reconciliation keeps the UI correct
          }
          const parsed = runEventSchema.safeParse(data);
          if (parsed.success) handlers.onEvent(parsed.data);
        });
      }
      source.addEventListener('end', (message) => {
        closed = true;
        source.close();
        handlers.onStatus('closed');
        try {
          const parsed = endSchema.safeParse(JSON.parse(message.data));
          if (parsed.success) handlers.onEnd(parsed.data.state);
        } catch {
          // ignore malformed frames
        }
      });
      return () => {
        closed = true;
        source.close();
      };
    },
  };
}
