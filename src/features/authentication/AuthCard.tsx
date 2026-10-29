import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Notice } from '@/components/ui/Notice';

interface AuthCardProps {
  title: string;
  subtitle: ReactNode;
  children: ReactNode;
  footer: ReactNode;
  providerConfigured: boolean;
}

export function AuthCard({ title, subtitle, children, footer, providerConfigured }: AuthCardProps) {
  return (
    <div className="animate-fade-in">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-[-0.02em] text-ink">{title}</h1>
        <p className="mt-2 text-sm text-muted">{subtitle}</p>
      </div>

      {!providerConfigured && (
        <Notice tone="info" className="mt-6">
          Accounts are not available yet, so no sign-in will succeed. You can still{' '}
          <Link to="/new" className="text-ink underline underline-offset-4">
            create a project
          </Link>
          ; it is saved in this browser.
        </Notice>
      )}

      <div className="mt-6 rounded-xl border border-line bg-surface p-6 shadow-panel">{children}</div>
      <p className="mt-6 text-center text-sm text-muted">{footer}</p>
    </div>
  );
}
