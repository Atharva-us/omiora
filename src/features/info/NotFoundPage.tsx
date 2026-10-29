import { ButtonLink } from '@/components/ui/Button';

export function NotFoundPage() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center px-4 py-28 text-center">
      <p className="font-mono text-sm text-cyan">404</p>
      <h1 className="mt-4 text-3xl font-semibold tracking-[-0.025em]">Page not found</h1>
      <p className="mt-3 text-muted">The page you are looking for does not exist or has moved.</p>
      <div className="mt-8 flex gap-3">
        <ButtonLink to="/">Go home</ButtonLink>
        <ButtonLink to="/projects" variant="secondary">
          View projects
        </ButtonLink>
      </div>
    </div>
  );
}
