/**
 * The ProjectService contract, run through the real HTTP adapter against a live Omniora API.
 *
 * Opt-in: set VITE_OMNIORA_CONTRACT_API_URL (for example http://127.0.0.1:8000) with the backend
 * running. Without it the suite is skipped, and reported as skipped, rather than faked.
 */
import { describe, it } from 'vitest';
import { describeProjectServiceContract } from '@/test/contracts/project-service.contract';
import { createHttpClient } from './http-client';
import { createHttpProjectService } from './project-service';

const API_URL = import.meta.env.VITE_OMNIORA_CONTRACT_API_URL as string | undefined;
const ORIGIN = 'http://localhost:5173';

/** Node's fetch has no cookie store, so emulate the browser's: keep the session cookie per "browser". */
function cookieJarFetch() {
  const cookies = new Map<string, string>();
  return async (input: string, init: RequestInit = {}) => {
    const headers = new Headers(init.headers);
    headers.set('Origin', ORIGIN);
    if (cookies.size) headers.set('Cookie', [...cookies].map(([name, value]) => `${name}=${value}`).join('; '));
    const response = await fetch(input, { ...init, headers });
    for (const cookie of response.headers.getSetCookie()) {
      const [pair] = cookie.split(';');
      const [name, ...rest] = (pair ?? '').split('=');
      if (name) cookies.set(name.trim(), rest.join('='));
    }
    return response;
  };
}

async function freshAccountService() {
  const fetchWithCookies = cookieJarFetch();
  const http = createHttpClient(API_URL!, fetchWithCookies);
  const email = `contract-${crypto.randomUUID()}@example.com`;
  await http.request('POST', '/api/v1/auth/register', { body: { name: 'Contract', email, password: 'contract-password' } });
  return createHttpProjectService(http);
}

if (API_URL) {
  describeProjectServiceContract(`http adapter against ${API_URL}`, freshAccountService);
} else {
  describe('ProjectService contract: http adapter against a live API', () => {
    it.skip('skipped: set VITE_OMNIORA_CONTRACT_API_URL to run against a running backend', () => {});
  });
}
