import { Bell, CreditCard, Database, FlaskConical, KeyRound, LayoutDashboard, type LucideIcon } from 'lucide-react';
import { CharacterCount, TextAreaField } from '@/components/ui/Field';
import { SelectableCard } from '@/components/ui/SelectableCard';
import { REQUIREMENTS } from '@/domain/projects/catalog';
import type { RequirementId } from '@/domain/projects/project';
import { PROJECT_LIMITS } from '@/domain/projects/rules';
import type { StepValidation, WizardAction, WizardDraft } from '../wizard-model';

const icons: Record<RequirementId, LucideIcon> = {
  authentication: KeyRound,
  database: Database,
  'admin-dashboard': LayoutDashboard,
  payments: CreditCard,
  notifications: Bell,
  'automated-tests': FlaskConical,
};

interface RequirementsStepProps {
  configuration: WizardDraft;
  dispatch: (action: WizardAction) => void;
  validation: StepValidation | null;
}

export function RequirementsStep({ configuration, dispatch, validation }: RequirementsStepProps) {
  const { features, custom } = configuration.requirements;
  return (
    <div className="space-y-6">
      <fieldset>
        <legend className="text-sm font-medium text-ink">Core features</legend>
        <p className="mt-1 text-[0.8125rem] text-faint">Select everything the first version should include.</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {REQUIREMENTS.map((requirement) => {
            const Icon = icons[requirement.id];
            return (
              <SelectableCard
                key={requirement.id}
                type="checkbox"
                name="requirements"
                value={requirement.id}
                checked={features.includes(requirement.id)}
                onChange={() => dispatch({ type: 'toggle-requirement', id: requirement.id })}
                title={requirement.label}
                description={requirement.description}
                icon={<Icon className="size-4" />}
              />
            );
          })}
        </div>
      </fieldset>

      <TextAreaField
        label="Additional requirements"
        name="custom"
        optional
        rows={4}
        value={custom}
        placeholder="e.g. Multi-language support, role-based permissions, export reports to CSV"
        error={validation?.fieldErrors.custom}
        trailing={<CharacterCount value={custom} max={PROJECT_LIMITS.customRequirementsMax} />}
        onChange={(event) => dispatch({ type: 'set-custom-requirements', value: event.target.value })}
      />
    </div>
  );
}
