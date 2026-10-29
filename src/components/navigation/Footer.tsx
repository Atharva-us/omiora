import { Link } from 'react-router-dom';
import { Logo } from '@/components/brand/Logo';

interface FooterLink {
  label: string;
  to: string | { pathname: string; hash: string };
}

const productLinks: FooterLink[] = [
  { label: 'Features', to: { pathname: '/', hash: 'features' } },
  { label: 'How It Works', to: { pathname: '/', hash: 'how-it-works' } },
  { label: 'Start a project', to: '/new' },
  { label: 'Projects', to: '/projects' },
];

const developerLinks: FooterLink[] = [
  { label: 'Developer approach', to: { pathname: '/', hash: 'developers' } },
  { label: 'Platform status', to: '/status' },
];

function FooterColumn({ title, links }: { title: string; links: FooterLink[] }) {
  return (
    <div>
      <h2 className="text-xs font-semibold tracking-[0.12em] text-faint uppercase">{title}</h2>
      <ul className="mt-4 space-y-2.5">
        {links.map((link) => (
          <li key={link.label}>
            <Link to={link.to} className="text-sm text-muted transition-colors hover:text-ink">
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t border-line-soft bg-obsidian">
      <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr]">
          <div className="max-w-sm">
            <Logo />
            <p className="mt-4 text-sm leading-relaxed text-muted">
              An AI-powered software engineering platform that transforms ideas into complete, testable, downloadable
              software.
            </p>
          </div>
          <FooterColumn title="Product" links={productLinks} />
          <FooterColumn title="Developers" links={developerLinks} />
        </div>
        <div className="mt-12 flex flex-col gap-4 border-t border-line-soft pt-6 text-sm text-faint sm:flex-row sm:items-center sm:justify-between">
          <p>© {year} Omniora. All rights reserved.</p>
          <ul className="flex gap-6">
            <li>
              <Link to="/privacy" className="hover:text-ink">
                Privacy
              </Link>
            </li>
            <li>
              <Link to="/terms" className="hover:text-ink">
                Terms
              </Link>
            </li>
          </ul>
        </div>
      </div>
    </footer>
  );
}
