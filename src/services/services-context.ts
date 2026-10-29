import { createContext } from 'react';
import type { KeyValueStore } from '@/infrastructure/storage/key-value-store';
import type { Logger } from '@/infrastructure/telemetry/logger';
import type { AuthenticationService } from './contracts/authentication-service';
import type { ProjectService } from './contracts/project-service';
import type { RequirementsService } from './contracts/requirements-service';
import type { RunService } from './contracts/run-service';

export type ServiceMode = 'demo' | 'api';

/**
 * Everything UI code may use, typed by interface only. Concrete adapters
 * are chosen in `app/composition/create-services.ts`; components never
 * construct or import an implementation.
 */
export interface Services {
  /** Which family of adapters is active. UI uses it only for labelling. */
  mode: ServiceMode;
  projects: ProjectService;
  auth: AuthenticationService;
  runs: RunService;
  requirements: RequirementsService;
  /** Session-scoped storage for non-sensitive UI state such as wizard drafts. */
  uiState: KeyValueStore;
  logger: Logger;
}

export const ServicesContext = createContext<Services | null>(null);
