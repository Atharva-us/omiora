import { isAppError } from '@/domain/errors';

/**
 * Rendered when configuration or service composition fails before the
 * router exists. Configuration messages are written by us and never echo
 * variable values, so they are safe to show.
 */
export function StartupErrorScreen({ error }: { error: unknown }) {
  const message =
    isAppError(error) && error.code === 'configuration'
      ? error.message
      : 'Omniora could not start. Reload the page, and if the problem continues, contact the site operator.';
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center px-4 text-center">
      <p className="font-mono text-xs tracking-[0.16em] text-warning">STARTUP FAILED</p>
      <h1 className="mt-4 text-2xl font-semibold text-ink">Omniora is not configured correctly</h1>
      <p role="alert" className="mt-3 max-w-xl text-sm leading-relaxed text-muted">
        {message}
      </p>
    </main>
  );
}
