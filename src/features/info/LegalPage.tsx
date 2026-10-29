import { Notice } from '@/components/ui/Notice';

interface LegalPageProps {
  kind: 'privacy' | 'terms';
}

const COPY = {
  privacy: {
    title: 'Privacy',
    summary:
      'In demo mode, project configurations and notes are stored only in your browser’s local storage and are not sent to any server. In API mode, they are stored by the Omniora backend for your account. In demo mode, passwords typed on the sign-in screens are neither stored nor transmitted. In API mode, they are sent to the backend over the connection you use and stored only as one-way Argon2id hashes. Typefaces are served from this site; no third-party font service is contacted.',
  },
  terms: {
    title: 'Terms',
    summary:
      'Omniora is currently a development preview. Features described as in development are not available, and no service-level commitments apply.',
  },
} as const;

export function LegalPage({ kind }: LegalPageProps) {
  const copy = COPY[kind];
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6 sm:py-20">
      <h1 className="text-3xl font-semibold tracking-[-0.025em] sm:text-4xl">{copy.title}</h1>
      <Notice tone="warning" className="mt-8" title="Policy not yet published">
        The formal {copy.title.toLowerCase()} policy will be published before accounts and cloud features launch.
      </Notice>
      <p className="mt-8 leading-relaxed text-muted">{copy.summary}</p>
    </div>
  );
}
