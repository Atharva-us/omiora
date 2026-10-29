import { useEffect } from 'react';
import { isRouteErrorResponse, Link, useRouteError } from 'react-router-dom';
import { RotateCcw } from 'lucide-react';
import { LogoMark } from '@/components/brand/Logo';
import { Button, ButtonLink } from '@/components/ui/Button';
import { toUserMessage } from '@/domain/errors';
import { useServices } from '@/hooks/use-services';

const FALLBACK = 'This page ran into a problem and could not be displayed. Your saved projects are not affected.';

/**
 * Route-level error boundary (`errorElement`). Shows a safe message and
 * recovery actions, logs the failure once, and reveals technical details
 * only in development builds.
 */
export function RouteErrorPage() {
  const error = useRouteError();
  const { logger } = useServices();

  useEffect(() => {
    logger.error('route.render-failed', { error });
  }, [error, logger]);

  const notFound = isRouteErrorResponse(error) && error.status === 404;
  const message = notFound ? 'The page you are looking for does not exist.' : toUserMessage(error, FALLBACK);

  return (
    <main id="main" className="flex min-h-dvh flex-col items-center justify-center px-4 py-16 text-center">
      <LogoMark size={44} />
      <h1 className="mt-6 text-2xl font-semibold tracking-[-0.02em] text-ink">
        {notFound ? 'Page not found' : 'Something went wrong'}
      </h1>
      <p role="alert" className="mt-3 max-w-md text-sm leading-relaxed text-muted">
        {message}
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Button onClick={() => window.location.reload()}>
          <RotateCcw aria-hidden="true" />
          Reload page
        </Button>
        <ButtonLink to="/" variant="secondary">
          Go home
        </ButtonLink>
      </div>
      <p className="mt-6 text-xs text-faint">
        If this keeps happening, check <Link to="/status" className="underline underline-offset-2">platform status</Link>.
      </p>
      {import.meta.env.DEV && error instanceof Error && (
        <details className="mt-8 w-full max-w-2xl rounded-lg border border-line bg-surface p-4 text-left">
          <summary className="cursor-pointer text-xs text-muted">Developer details (development builds only)</summary>
          <pre className="scrollbar-thin mt-3 overflow-auto font-mono text-xs whitespace-pre-wrap text-faint">
            {error.stack ?? error.message}
          </pre>
        </details>
      )}
    </main>
  );
}
