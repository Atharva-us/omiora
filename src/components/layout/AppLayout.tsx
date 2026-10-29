import { NavLink, Outlet } from 'react-router-dom';
import { FolderKanban, Plus } from 'lucide-react';
import { Logo } from '@/components/brand/Logo';
import { AccountControl } from '@/components/navigation/AccountControl';
import { ButtonLink } from '@/components/ui/Button';
import { useScrollToHash } from '@/hooks/use-scroll-to-hash';
import { cn } from '@/lib/cn';
import { SkipLink } from './SkipLink';

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'inline-flex h-8 items-center gap-2 rounded-md px-3 text-sm transition-colors',
    isActive ? 'bg-elevated text-ink' : 'text-muted hover:text-ink',
  );

/** Shell for the signed-in style product surfaces (dashboard, wizard, workspace). */
export function AppLayout() {
  useScrollToHash();
  return (
    <div className="flex min-h-dvh flex-col">
      <SkipLink />
      <header className="sticky top-0 z-40 border-b border-line-soft bg-obsidian/95 backdrop-blur-md">
        <nav aria-label="Application" className="flex h-14 items-center justify-between gap-4 px-4 sm:px-6">
          <div className="flex items-center gap-4 sm:gap-6">
            <Logo to="/" size={28} />
            <span aria-hidden="true" className="hidden h-5 w-px bg-line sm:block" />
            <NavLink to="/projects" end className={navLinkClass}>
              <FolderKanban aria-hidden="true" className="size-4" />
              <span className="hidden sm:inline">Projects</span>
              <span className="sr-only sm:hidden">Projects</span>
            </NavLink>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden sm:block">
              <AccountControl />
            </div>
            <ButtonLink to="/new" size="sm">
              <Plus aria-hidden="true" />
              New Project
            </ButtonLink>
          </div>
        </nav>
      </header>
      <main id="main" className="flex flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  );
}
