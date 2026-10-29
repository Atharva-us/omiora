import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { createServices } from '@/app/composition/create-services';
import { parseAppConfig } from '@/app/configuration/app-config';
import { StartupErrorScreen } from '@/app/error-handling/StartupErrorScreen';
import { ServicesProvider } from '@/app/providers/ServicesProvider';
import { SessionProvider } from '@/app/providers/SessionProvider';
import { createAppRouter } from '@/app/router/router';
// Self-hosted typefaces (SIL OFL 1.1; licence texts ship in /licenses).
import '@fontsource-variable/geist';
import '@fontsource-variable/geist-mono';
import '@/styles/index.css';

const root = document.getElementById('root');
if (!root) throw new Error('Root element #root not found.');

function bootstrap() {
  try {
    const services = createServices(parseAppConfig(import.meta.env));
    return (
      <ServicesProvider services={services}>
        <SessionProvider>
          <RouterProvider router={createAppRouter()} />
        </SessionProvider>
      </ServicesProvider>
    );
  } catch (error) {
    console.error('[omniora] startup failed', error);
    return <StartupErrorScreen error={error} />;
  }
}

createRoot(root).render(<StrictMode>{bootstrap()}</StrictMode>);
