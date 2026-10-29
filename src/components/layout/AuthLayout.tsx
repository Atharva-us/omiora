import { Link, Outlet } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { LogoMark } from '@/components/brand/Logo';
import { useScrollToHash } from '@/hooks/use-scroll-to-hash';

export function AuthLayout() {
  useScrollToHash();
  return (
    <div className="relative flex min-h-dvh flex-col">
      <div aria-hidden="true" className="bg-grid pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black,transparent_70%)]" />
      <header className="relative flex h-16 items-center px-4 sm:px-6">
        <Link to="/" className="inline-flex items-center gap-2 rounded-md text-sm text-muted hover:text-ink">
          <ArrowLeft aria-hidden="true" className="size-4" />
          Back to Omniora
        </Link>
      </header>
      <main id="main" className="relative flex flex-1 items-start justify-center px-4 pt-6 pb-16 sm:items-center sm:pt-0">
        <div className="w-full max-w-[400px]">
          <div className="mb-8 flex flex-col items-center text-center">
            <LogoMark size={48} />
          </div>
          <Outlet />
        </div>
      </main>
    </div>
  );
}
