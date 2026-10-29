import { z } from 'zod/mini';
import { AppError } from '@/domain/errors';
import {
  approvedRequirementsSchema,
  sessionDetailSchema,
  sessionSchema,
  versionSchema,
  versionSummarySchema,
} from '@/domain/requirements/requirements';
import type { RequirementsService } from '../contracts/requirements-service';
import type { HttpClient } from './http-client';

/** RequirementsService over the FastAPI backend (docs/BACKEND_CONTRACTS.md §5.1). */
export function createHttpRequirementsService(http: HttpClient): RequirementsService {
  const project = (id: string) => `/api/v1/projects/${encodeURIComponent(id)}`;
  const session = (id: string) => `/api/v1/requirements-sessions/${encodeURIComponent(id)}`;
  return {
    available: true,
    listSessions: (projectId) =>
      http.request('GET', `${project(projectId)}/requirements-sessions`, { schema: z.array(sessionSchema) }),
    getSession: (sessionId) => http.request('GET', session(sessionId), { schema: sessionDetailSchema }),
    startSession: (projectId, idempotencyKey) =>
      http.request('POST', `${project(projectId)}/requirements-sessions`, {
        headers: { 'Idempotency-Key': idempotencyKey },
        schema: sessionSchema,
      }),
    submitAnswers: (sessionId, idempotencyKey, answers, advance) =>
      http.request('POST', `${session(sessionId)}/answers`, {
        headers: { 'Idempotency-Key': idempotencyKey },
        body: { answers, advance },
        schema: sessionDetailSchema,
      }),
    retryTurn: (sessionId) => http.request('POST', `${session(sessionId)}/turns/retry`, { schema: sessionDetailSchema }),
    submitForApproval: (sessionId, version) =>
      http.request('POST', `${session(sessionId)}/submit`, { body: { version }, schema: sessionDetailSchema }),
    decide: (sessionId, approvalId, input) =>
      http.request('POST', `${session(sessionId)}/approvals/${encodeURIComponent(approvalId)}`, {
        body: input,
        schema: sessionDetailSchema,
      }),
    cancel: (sessionId) => http.request('POST', `${session(sessionId)}/cancel`, { schema: sessionDetailSchema }),
    listVersions: (sessionId) =>
      http.request('GET', `${session(sessionId)}/versions`, { schema: z.array(versionSummarySchema) }),
    getVersion: (sessionId, version, diffFrom) =>
      http.request('GET', `${session(sessionId)}/versions/${version}${diffFrom ? `?diff=${diffFrom}` : ''}`, {
        schema: versionSchema,
      }),
    async getApproved(projectId) {
      try {
        return await http.request('GET', `${project(projectId)}/requirements/approved`, {
          schema: approvedRequirementsSchema,
        });
      } catch (error) {
        if (error instanceof AppError && error.code === 'not-found') return null;
        throw error;
      }
    },
  };
}
