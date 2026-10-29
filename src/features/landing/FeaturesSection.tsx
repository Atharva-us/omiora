import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { FEATURES } from './content';

export function FeaturesSection() {
  return (
    <section id="features" aria-labelledby="features-heading" className="border-t border-line-soft py-20 sm:py-28">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr] lg:items-end">
          <div>
            <p className="font-mono text-xs tracking-[0.16em] text-cyan">CAPABILITIES</p>
            <h2 id="features-heading" className="mt-4 text-3xl font-semibold tracking-[-0.025em] sm:text-4xl">
              Engineered end to end, from intent to export.
            </h2>
          </div>
          <p className="text-muted lg:justify-self-end lg:text-right">
            Omniora is under active development. Each capability below is labelled with its current state.{' '}
            <Link to="/status" className="inline-flex items-center gap-1 text-ink underline-offset-4 hover:underline">
              View platform status
              <ArrowRight aria-hidden="true" className="size-3.5" />
            </Link>
          </p>
        </div>

        <ul className="mt-12 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ title, description, icon: Icon, availability }) => (
            <li key={title} className="flex flex-col bg-surface p-6 sm:p-7">
              <div className="flex items-center justify-between">
                <Icon aria-hidden="true" className="size-5 text-cyan" strokeWidth={1.75} />
                {availability === 'preview' ? (
                  <Badge tone="info">Preview available</Badge>
                ) : (
                  <Badge>In development</Badge>
                )}
              </div>
              <h3 className="mt-6 text-base font-semibold text-ink">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{description}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
