import { Layers, Wand2 } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Notice } from '@/components/ui/Notice';
import { SelectableCard } from '@/components/ui/SelectableCard';
import { CATEGORY_LABELS, CATEGORY_ORDER, TECHNOLOGIES } from '@/domain/projects/catalog';
import type { StepValidation, WizardAction, WizardDraft } from '../wizard-model';

interface StackStepProps {
  configuration: WizardDraft;
  dispatch: (action: WizardAction) => void;
  validation: StepValidation;
  showAllErrors: boolean;
}

export function StackStep({ configuration, dispatch, validation, showAllErrors }: StackStepProps) {
  const { stack } = configuration;
  const isCustom = stack.mode === 'custom';
  // Compatibility problems are shown as soon as they occur; the "nothing selected"
  // error waits until the user tries to continue.
  const visibleErrors = showAllErrors || stack.technologies.length > 0 ? validation.stackErrors : [];

  return (
    <div className="space-y-6">
      <fieldset>
        <legend className="text-sm font-medium text-ink">How should the stack be chosen?</legend>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          <SelectableCard
            type="radio"
            name="stack-mode"
            value="recommend"
            checked={!isCustom}
            onChange={() => dispatch({ type: 'set-stack-mode', mode: 'recommend' })}
            title="Recommend a stack for me"
            description="The planning service will propose technologies based on your requirements."
            icon={<Wand2 className="size-4" />}
          />
          <SelectableCard
            type="radio"
            name="stack-mode"
            value="custom"
            checked={isCustom}
            onChange={() => dispatch({ type: 'set-stack-mode', mode: 'custom' })}
            title="I'll choose my stack"
            description="Select the frameworks, runtime, and database you prefer."
            icon={<Layers className="size-4" />}
          />
        </div>
      </fieldset>

      {!isCustom && (
        <Notice tone="info" title="Recommendation is pending the planning service">
          Your project will be saved with a request for a recommended stack. The recommendation is produced once the
          planning service is connected; nothing is selected automatically today.
        </Notice>
      )}

      {isCustom && (
        <>
          <Notice tone="info">
            Code generators are not connected yet. Your selection is saved as a preference and validated for
            compatibility with your platform.
          </Notice>

          {CATEGORY_ORDER.map((category) => (
            <fieldset key={category}>
              <legend className="text-xs font-semibold tracking-[0.12em] text-faint uppercase">
                {CATEGORY_LABELS[category]}
              </legend>
              <div className="mt-2 grid gap-3 sm:grid-cols-2">
                {TECHNOLOGIES.filter((technology) => technology.category === category).map((technology) => (
                  <SelectableCard
                    key={technology.id}
                    type="checkbox"
                    name="technologies"
                    value={technology.id}
                    checked={stack.technologies.includes(technology.id)}
                    onChange={() => dispatch({ type: 'toggle-technology', id: technology.id })}
                    title={technology.name}
                    description={technology.description}
                    meta={<Badge className="ml-auto">Planned</Badge>}
                  />
                ))}
              </div>
            </fieldset>
          ))}

          {visibleErrors.length > 0 && (
            <Notice tone="danger" role="alert" title="This stack needs attention">
              <ul className="list-disc space-y-1 pl-4">
                {visibleErrors.map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            </Notice>
          )}
          {validation.stackWarnings.length > 0 && (
            <Notice tone="warning" title="Things to consider">
              <ul className="list-disc space-y-1 pl-4">
                {validation.stackWarnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </Notice>
          )}
        </>
      )}
    </div>
  );
}
