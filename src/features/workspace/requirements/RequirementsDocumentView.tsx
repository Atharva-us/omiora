import type { ReactNode } from 'react';
import { CircleDot } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { groupByPriority, type RequirementsVersion } from '@/domain/requirements/requirements';
import { SOURCE_LABELS } from './requirements-model';

const PRIORITY_LABELS = { must: 'Must have', should: 'Should have', could: 'Could have', wont: "Won't have (this version)" };

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title}>
      <h3 className="text-[0.6875rem] font-semibold tracking-[0.12em] text-faint uppercase">{title}</h3>
      <div className="mt-2">{children}</div>
    </section>
  );
}

/** The structured requirements of one version: context, requirements by priority, assumptions. */
export function RequirementsDocumentView({ version }: { version: RequirementsVersion }) {
  const { content } = version;
  const deprecated = content.requirements.filter((r) => r.status === 'deprecated');
  return (
    <div className="space-y-6">
      <Section title="Project context">
        <dl className="grid gap-x-6 gap-y-2 rounded-lg border border-line bg-surface p-4 text-sm sm:grid-cols-[8rem_1fr]">
          <dt className="text-faint">Goal</dt>
          <dd className="text-ink">{content.context.goal}</dd>
          {content.context.scope && (
            <>
              <dt className="text-faint">Scope</dt>
              <dd className="text-ink">{content.context.scope}</dd>
            </>
          )}
          <dt className="text-faint">Tenancy</dt>
          <dd className="text-ink">
            {content.context.tenancy === 'multi'
              ? 'Multi-tenant: separate customers share one deployment'
              : content.context.tenancy === 'single'
                ? 'Single tenant'
                : 'Unknown (being asked)'}
          </dd>
          {content.context.personas.length > 0 && (
            <>
              <dt className="text-faint">Users</dt>
              <dd className="text-ink">{content.context.personas.map((p) => p.name).join(', ')}</dd>
            </>
          )}
          {content.context.outOfScope.length > 0 && (
            <>
              <dt className="text-faint">Out of scope</dt>
              <dd className="text-ink">{content.context.outOfScope.join('; ')}</dd>
            </>
          )}
        </dl>
      </Section>

      {groupByPriority(content.requirements).map(({ priority, items }) => (
        <Section key={priority} title={`${PRIORITY_LABELS[priority]} (${items.length})`}>
          <ul className="space-y-2">
            {items.map((requirement) => (
              <li key={requirement.id} className="rounded-lg border border-line bg-surface p-3">
                <div className="flex flex-wrap items-start gap-2">
                  <span className="font-mono text-xs text-faint">{requirement.id}</span>
                  <p className="flex-1 text-sm text-ink">{requirement.statement}</p>
                  {requirement.tags.includes('tenant-isolation') && <Badge tone="info">tenant isolation</Badge>}
                  <Badge tone={requirement.confidence === 'high' ? 'success' : requirement.confidence === 'medium' ? 'neutral' : 'warning'}>
                    {requirement.confidence} confidence
                  </Badge>
                </div>
                <p className="mt-1 pl-14 text-xs text-faint">
                  {SOURCE_LABELS[requirement.source]}
                  {requirement.evidence.length > 0 && ` · ${requirement.evidence.join(', ')}`}
                </p>
                <ul className="mt-2 space-y-1 pl-14 text-[0.8125rem] text-muted">
                  {requirement.acceptanceCriteria.map((criterion) => (
                    <li key={criterion} className="flex gap-2">
                      <CircleDot aria-hidden="true" className="mt-0.5 size-3 shrink-0 text-faint" />
                      {criterion}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </Section>
      ))}

      {content.assumptions.length > 0 && (
        <Section title="Assumptions">
          <ul className="space-y-1.5 text-sm text-muted">
            {content.assumptions.map((assumption) => (
              <li key={assumption.statement} className="flex flex-wrap items-center gap-2">
                <span className="flex-1">{assumption.statement}</span>
                <Badge tone={assumption.confidence === 'low' ? 'warning' : 'neutral'}>{assumption.confidence}</Badge>
                {assumption.basis.length > 0 && <span className="font-mono text-xs text-faint">for {assumption.basis.join(', ')}</span>}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {deprecated.length > 0 && (
        <Section title={`Deprecated (${deprecated.length})`}>
          <ul className="space-y-1 text-sm text-faint">
            {deprecated.map((requirement) => (
              <li key={requirement.id}>
                <span className="font-mono text-xs">{requirement.id}</span> <s>{requirement.statement}</s>
                {requirement.deprecationReason && ` (${requirement.deprecationReason})`}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}
