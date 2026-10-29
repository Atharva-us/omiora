import { describe, expect, it } from 'vitest';
import { AppError } from '@/domain/errors';
import { parseAppConfig } from './app-config';

const configError = (env: Record<string, unknown>) => {
  try {
    parseAppConfig(env);
  } catch (error) {
    expect(error).toBeInstanceOf(AppError);
    expect((error as AppError).code).toBe('configuration');
    return (error as AppError).message;
  }
  throw new Error('Expected a configuration error');
};

describe('parseAppConfig', () => {
  it('defaults to demo mode only in development', () => {
    expect(parseAppConfig({ DEV: true })).toEqual({ serviceMode: 'demo', logLevel: 'debug', isDevelopment: true });
    expect(parseAppConfig({ VITE_OMNIORA_SERVICE_MODE: 'demo' })).toEqual({
      serviceMode: 'demo',
      logLevel: 'warn',
      isDevelopment: false,
    });
    expect(parseAppConfig({ DEV: true, VITE_OMNIORA_LOG_LEVEL: 'error' }).logLevel).toBe('error');
  });

  it('requires production builds to choose a mode explicitly', () => {
    expect(configError({})).toMatch(/must be set to "demo" or "api" for production builds/);
  });

  it('rejects unknown modes and log levels', () => {
    expect(configError({ VITE_OMNIORA_SERVICE_MODE: 'production' })).toMatch(/must be "demo" or "api"/);
    expect(configError({ DEV: true, VITE_OMNIORA_LOG_LEVEL: 'verbose' })).toMatch(/LOG_LEVEL/);
  });

  it('requires a secure API base URL in api mode', () => {
    expect(configError({ VITE_OMNIORA_SERVICE_MODE: 'api' })).toMatch(/API_BASE_URL is required/);
    expect(configError({ VITE_OMNIORA_SERVICE_MODE: 'api', VITE_OMNIORA_API_BASE_URL: 'not a url' })).toMatch(/absolute URL/);
    expect(
      configError({ VITE_OMNIORA_SERVICE_MODE: 'api', VITE_OMNIORA_API_BASE_URL: 'http://api.example.com' }),
    ).toMatch(/https/);
    expect(
      configError({ VITE_OMNIORA_SERVICE_MODE: 'api', VITE_OMNIORA_API_BASE_URL: 'https://user:pw@api.example.com' }),
    ).toMatch(/credentials/);
    expect(
      parseAppConfig({ VITE_OMNIORA_SERVICE_MODE: 'api', VITE_OMNIORA_API_BASE_URL: 'https://api.example.com/v1/' }),
    ).toMatchObject({ serviceMode: 'api', apiBaseUrl: 'https://api.example.com/v1' });
    expect(
      parseAppConfig({ DEV: true, VITE_OMNIORA_SERVICE_MODE: 'api', VITE_OMNIORA_API_BASE_URL: 'http://localhost:8000' }),
    ).toMatchObject({ apiBaseUrl: 'http://localhost:8000' });
  });

  it('refuses to start when a secret-looking variable is exposed to the bundle', () => {
    const message = configError({ DEV: true, VITE_OPENAI_API_KEY: 'sk-live-123' });
    expect(message).toMatch(/VITE_OPENAI_API_KEY looks like a secret/);
    expect(message).not.toContain('sk-live-123');
  });
});
