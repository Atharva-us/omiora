import { createBrowserStore, type KeyValueStore } from '@/infrastructure/storage/key-value-store';
import { createConsoleLogger, type Logger } from '@/infrastructure/telemetry/logger';
import { createLocalProjectService } from '@/services/demo/local-project-service';
import { createHttpAuthService } from '@/services/http/authentication-service';
import { createHttpClient } from '@/services/http/http-client';
import { createHttpProjectService } from '@/services/http/project-service';
import { createHttpRunService, type EventSourceFactory } from '@/services/http/run-service';
import type { Services } from '@/services/services-context';
import { createUnconfiguredAuthService } from '@/services/unconfigured/authentication-service';
import { createUnavailableRunService } from '@/services/unconfigured/run-service';
import type { AppConfig } from '../configuration/app-config';

/** Overrides for tests; production code passes only the config. */
export interface CompositionOverrides {
  projectStore?: KeyValueStore;
  uiStateStore?: KeyValueStore;
  logger?: Logger;
  now?: () => Date;
  fetch?: (input: string, init?: RequestInit) => Promise<Response>;
  eventSource?: EventSourceFactory;
}

/**
 * COMPOSITION ROOT: the only place that knows which concrete adapters back
 * each service. Demo mode uses browser storage and has no agent runs; API
 * mode talks to the FastAPI backend. There is no fallback between the two.
 */
export function createServices(config: AppConfig, overrides: CompositionOverrides = {}): Services {
  const logger =
    overrides.logger ?? createConsoleLogger({ minLevel: config.logLevel, includeStacks: config.isDevelopment });
  const uiState = overrides.uiStateStore ?? createBrowserStore('session');

  if (config.serviceMode === 'api') {
    const http = createHttpClient(config.apiBaseUrl, overrides.fetch);
    return {
      mode: 'api',
      projects: createHttpProjectService(http),
      auth: createHttpAuthService(http),
      runs: createHttpRunService(http, overrides.eventSource),
      uiState,
      logger,
    };
  }

  return {
    mode: 'demo',
    projects: createLocalProjectService({
      store: overrides.projectStore ?? createBrowserStore('local'),
      logger,
      ...(overrides.now ? { now: overrides.now } : {}),
    }),
    auth: createUnconfiguredAuthService(),
    runs: createUnavailableRunService(),
    uiState,
    logger,
  };
}
