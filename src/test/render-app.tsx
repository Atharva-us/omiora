import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { createServices, type CompositionOverrides } from '@/app/composition/create-services';
import { parseAppConfig } from '@/app/configuration/app-config';
import { ServicesProvider } from '@/app/providers/ServicesProvider';
import { SessionProvider } from '@/app/providers/SessionProvider';
import { routes } from '@/app/router/routes';
import { createMemoryLogger } from '@/infrastructure/telemetry/logger';
import type { Services } from '@/services/services-context';

/**
 * Builds services through the real composition root in demo mode, backed by
 * jsdom's localStorage/sessionStorage (cleared after each test) and a memory
 * logger so tests can assert on diagnostics without console noise.
 */
export function createTestServices(overrides: CompositionOverrides = {}): TestServices {
  const memoryLogger = createMemoryLogger();
  const services = createServices(parseAppConfig({ VITE_OMNIORA_SERVICE_MODE: 'demo' }), {
    logger: memoryLogger,
    ...overrides,
  });
  return { ...services, memoryLogger };
}

export type TestServices = Services & { memoryLogger: ReturnType<typeof createMemoryLogger> };

interface RenderAppOptions {
  route?: string;
  services?: TestServices;
}

/** Renders the full route tree in memory. */
export function renderApp({ route = '/', services = createTestServices() }: RenderAppOptions = {}) {
  const router = createMemoryRouter(routes, { initialEntries: [route] });
  const user = userEvent.setup();
  const result = render(
    <ServicesProvider services={services}>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </ServicesProvider>,
  );
  return { ...result, router, services, user };
}
