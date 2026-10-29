import type { ReactNode } from 'react';
import { Pencil } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { PLATFORM_LABELS, requirementLabel, technologyNames } from '@/domain/projects/catalog';
import type { ProjectConfiguration } from '@/domain/projects/project';

interface ReviewStepProps {
  configuration: ProjectConfiguration;
  onEdit: (step: number) => void;
}

function Section({
  title,
  step,
  onEdit,
  children,
}: {
  title: string;
  step: number;
  onEdit: (step: number) => void;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-line bg-surface" aria-label={title}>
      <div className="flex items-center justify-between border-b border-line-soft px-4 py-3">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        <Button variant="ghost" size="sm" onClick={() => onEdit(step)} aria-label={`Edit ${title.toLowerCase()}`}>
          <Pencil aria-hidden="true" />
          Edit
        </Button>
      </div>
      <dl className="divide-y divide-line-soft">{children}</dl>
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 px-4 py-3 sm:grid-cols-[160px_1fr] sm:gap-4">
      <dt className="text-[0.8125rem] text-faint">{label}</dt>
      <dd className="min-w-0 text-sm break-words text-ink">{children}</dd>
    </div>
  );
}

const none = <span className="text-faint">None</span>;

export function ReviewStep({ configuration, onEdit }: ReviewStepProps) {
  const { stack, requirements } = configuration;
  return (
    <div className="space-y-4">
      <Section title="Project idea" step={0} onEdit={onEdit}>
        <Row label="Name">{configuration.name}</Row>
        <Row label="Description">
          <span className="whitespace-pre-line">{configuration.description}</span>
        </Row>
        <Row label="Platform">{PLATFORM_LABELS[configuration.platform]}</Row>
        <Row label="Design reference">{configuration.referenceUrl || none}</Row>
      </Section>

      <Section title="Technology" step={1} onEdit={onEdit}>
        <Row label="Approach">{stack.mode === 'recommend' ? 'Recommend a stack for me' : 'Custom stack'}</Row>
        {stack.mode === 'custom' && (
          <Row label="Technologies">
            <span className="flex flex-wrap gap-1.5">
              {technologyNames(stack.technologies).map((name) => (
                <Badge key={name}>{name}</Badge>
              ))}
            </span>
          </Row>
        )}
      </Section>

      <Section title="Requirements" step={2} onEdit={onEdit}>
        <Row label="Core features">
          {requirements.features.length > 0 ? (
            <span className="flex flex-wrap gap-1.5">
              {requirements.features.map((id) => (
                <Badge key={id}>{requirementLabel(id)}</Badge>
              ))}
            </span>
          ) : (
            none
          )}
        </Row>
        <Row label="Additional">
          {requirements.custom ? (
            <span className="whitespace-pre-line">{requirements.custom}</span>
          ) : (
            none
          )}
        </Row>
      </Section>
    </div>
  );
}
