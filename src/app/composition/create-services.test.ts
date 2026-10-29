import { describe, expect, it, vi } from 'vitest';
import { createMemoryStore } from '@/infrastructure/storage/key-value-store';
import { createMemoryLogger } from '@/infrastructure/telemetry/logger';
import { validConfiguration } from '@/test/fixtures';
import { parseAppConfig } from '../configuration/app-config';
import { createServices } from './create-services';

describe('createServices', () => {
  it('wires demo adapters in demo mode and never claims real authentication or agent runs', async () => {
    const services = createServices(parseAppConfig({ VITE_OMNIORA_SERVICE_MODE: 'demo' }), {
      projectStore: createMemoryStore(),
      uiStateStore: createMemoryStore(),
      logger: createMemoryLogger(),
    });
    expect(services.mode).toBe('demo');
    expect(services.auth.isConfigured).toBe(false);
    expect(services.runs.available).toBe(false);
    await expect(services.auth.signIn({ email: 'a@b.co', password: 'x' })).rejects.toMatchObject({
      code: 'provider-not-configured',
    });
    await expect(services.runs.startPlanning('prj_1', 'key-12345678')).rejects.toMatchObject({
      code: 'provider-not-configured',
    });
    const project = await services.projects.createProject(validConfiguration());
    expect(await services.projects.getProject(project.id)).toEqual(project);
  });

  it('wires HTTP adapters in api mode, with credentials and the CSRF header, and no demo storage', async () => {
    const fetch = vi.fn(async () => new Response(JSON.stringify({ items: [], nextCursor: null }), { status: 200 }));
    const projectStore = createMemoryStore();
    const services = createServices(
      parseAppConfig({ VITE_OMNIORA_SERVICE_MODE: 'api', VITE_OMNIORA_API_BASE_URL: 'https://api.example.com' }),
      { fetch, projectStore, uiStateStore: createMemoryStore(), logger: createMemoryLogger() },
    );
    expect(services.mode).toBe('api');
    expect(services.auth.isConfigured).toBe(true);
    expect(services.runs.available).toBe(true);
    expect(await services.projects.listProjects()).toEqual([]);
    expect(fetch).toHaveBeenCalledWith(
      'https://api.example.com/api/v1/projects?limit=100',
      expect.objectContaining({ credentials: 'include', headers: expect.objectContaining({ 'X-Omniora-Client': 'web' }) }),
    );
    expect(projectStore.get('omniora.demo.v1')).toBeUndefined();
  });
});
