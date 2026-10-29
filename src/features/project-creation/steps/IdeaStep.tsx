import { Globe, MonitorSmartphone, Smartphone } from 'lucide-react';
import { CharacterCount, TextAreaField, TextField } from '@/components/ui/Field';
import { SelectableCard } from '@/components/ui/SelectableCard';
import type { PlatformTarget } from '@/domain/projects/project';
import { PROJECT_LIMITS } from '@/domain/projects/rules';
import type { StepValidation, WizardAction, WizardDraft } from '../wizard-model';

const platforms: { id: PlatformTarget; title: string; description: string; icon: typeof Globe }[] = [
  { id: 'website', title: 'Website', description: 'Responsive web application or site.', icon: Globe },
  { id: 'mobile', title: 'Mobile app', description: 'iOS and Android application.', icon: Smartphone },
  { id: 'both', title: 'Both', description: 'Web and mobile from one project.', icon: MonitorSmartphone },
];

interface IdeaStepProps {
  configuration: WizardDraft;
  dispatch: (action: WizardAction) => void;
  validation: StepValidation | null;
}

export function IdeaStep({ configuration, dispatch, validation }: IdeaStepProps) {
  const errors = validation?.fieldErrors ?? {};
  return (
    <div className="space-y-6">
      <TextField
        label="Project name"
        name="name"
        value={configuration.name}
        autoComplete="off"
        placeholder="e.g. Atelier Commerce"
        error={errors.name}
        trailing={<CharacterCount value={configuration.name} max={PROJECT_LIMITS.nameMax} />}
        onChange={(event) => dispatch({ type: 'update', patch: { name: event.target.value } })}
      />

      <TextAreaField
        label="Project description"
        name="description"
        rows={5}
        value={configuration.description}
        placeholder="Describe the software you want to build, who it is for, and the key things it should do."
        error={errors.description}
        hint="Plain language is fine. More detail leads to a better plan."
        trailing={<CharacterCount value={configuration.description} max={PROJECT_LIMITS.descriptionMax} />}
        onChange={(event) => dispatch({ type: 'update', patch: { description: event.target.value } })}
      />

      <fieldset>
        <legend className="text-sm font-medium text-ink">What are you building?</legend>
        <div className="mt-2 grid gap-3 sm:grid-cols-3">
          {platforms.map(({ id, title, description, icon: Icon }) => (
            <SelectableCard
              key={id}
              type="radio"
              name="platform"
              value={id}
              checked={configuration.platform === id}
              onChange={() => dispatch({ type: 'update', patch: { platform: id } })}
              title={title}
              description={description}
              icon={<Icon className="size-4" />}
            />
          ))}
        </div>
      </fieldset>

      <TextField
        label="Design reference URL"
        name="referenceUrl"
        type="url"
        inputMode="url"
        optional
        value={configuration.referenceUrl}
        placeholder="https://example.com"
        error={errors.referenceUrl}
        hint="Saved with your configuration. Reference analysis is not connected yet."
        onChange={(event) => dispatch({ type: 'update', patch: { referenceUrl: event.target.value } })}
      />
    </div>
  );
}
