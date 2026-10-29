import { Badge } from '@/components/ui/Badge';
import type { BadgeTone } from '@/components/ui/Badge';
import { useServices } from '@/hooks/use-services';
import { capabilitiesFor, type CapabilityStatus } from '@/services/capabilities';

const STATUS_DISPLAY: Record<CapabilityStatus, { label: string; tone: BadgeTone }> = {
  available: { label: 'Available', tone: 'success' },
  demo: { label: 'Demo (local only)', tone: 'info' },
  'not-connected': { label: 'Not connected', tone: 'neutral' },
};

export function StatusPage() {
  const { mode } = useServices();
  return (
    <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 sm:py-20">
      <p className="font-mono text-xs tracking-[0.16em] text-cyan">PLATFORM STATUS</p>
      <h1 className="mt-4 text-3xl font-semibold tracking-[-0.025em] sm:text-4xl">What works today</h1>
      <p className="mt-4 max-w-2xl text-muted">
        Omniora is in its first development phase. This page lists every platform capability and whether it is
        actually connected in this build. Nothing marked &ldquo;not connected&rdquo; is simulated anywhere in the
        interface.
      </p>
      <p className="mt-3 text-sm text-faint">
        This build is running in <span className="font-medium text-ink">{mode === 'api' ? 'API' : 'demo'} mode</span>.
      </p>

      <ul className="mt-10 divide-y divide-line-soft rounded-xl border border-line bg-surface">
        {capabilitiesFor(mode).map((capability) => {
          const display = STATUS_DISPLAY[capability.status];
          return (
            <li key={capability.id} className="flex flex-col gap-2 p-5 sm:flex-row sm:items-start sm:justify-between sm:gap-8">
              <div>
                <h2 className="text-sm font-semibold text-ink">{capability.name}</h2>
                <p className="mt-1 text-sm leading-relaxed text-muted">{capability.detail}</p>
              </div>
              <Badge tone={display.tone} dot className="self-start">
                {display.label}
              </Badge>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
