import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { Logo } from '@/components/brand/Logo';
import { ButtonLink } from '@/components/ui/Button';
import { AccountControl } from './AccountControl';
import { cn } from '@/lib/cn';
import { SECTION_LINKS } from './nav-links';

export function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const location = useLocation();
  const [lastLocationKey, setLastLocationKey] = useState(location.key);

  // Close the mobile menu whenever navigation happens.
  if (lastLocationKey !== location.key) {
    setLastLocationKey(location.key);
    setMenuOpen(false);
  }

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [menuOpen]);

  return (
    <header
      className={cn(
        'sticky top-0 z-40 border-b transition-colors',
        scrolled || menuOpen ? 'border-line-soft bg-obsidian/90 backdrop-blur-md' : 'border-transparent bg-transparent',
      )}
    >
      <nav aria-label="Main" className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-6 px-4 sm:px-6 lg:px-8">
        <Logo />

        <ul className="hidden items-center gap-1 md:flex">
          {SECTION_LINKS.map((link) => (
            <li key={link.hash}>
              <Link
                to={{ pathname: '/', hash: link.hash }}
                className="rounded-md px-3 py-2 text-sm text-muted transition-colors hover:text-ink"
              >
                {link.label}
              </Link>
            </li>
          ))}
        </ul>

        <div className="hidden items-center gap-2 md:flex">
          <AccountControl />
          <ButtonLink to="/new" size="sm">
            Start Building
          </ButtonLink>
        </div>

        <button
          type="button"
          className="-mr-2 rounded-md p-2 text-muted hover:text-ink md:hidden"
          aria-expanded={menuOpen}
          aria-controls="mobile-menu"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? <X aria-hidden="true" className="size-5" /> : <Menu aria-hidden="true" className="size-5" />}
        </button>
      </nav>

      {menuOpen && (
        <div id="mobile-menu" className="animate-fade-in border-t border-line-soft px-4 pt-2 pb-5 md:hidden">
          <ul className="flex flex-col">
            {SECTION_LINKS.map((link) => (
              <li key={link.hash}>
                <Link
                  to={{ pathname: '/', hash: link.hash }}
                  onClick={() => setMenuOpen(false)}
                  className="block rounded-md px-2 py-3 text-[0.9375rem] text-muted hover:bg-elevated hover:text-ink"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <AccountControl size="md" />
            <ButtonLink to="/new">Start Building</ButtonLink>
          </div>
        </div>
      )}
    </header>
  );
}
