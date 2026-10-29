import { z } from 'zod/mini';
import {
  projectConfigurationSchema,
  technologyIdSchema,
  type ProjectConfiguration,
  type RequirementId,
  type StackMode,
  type StackPreference,
  type TechnologyId,
} from '@/domain/projects/project';
import {
  normalizeConfiguration,
  PROJECT_LIMITS,
  validateCustomRequirements,
  validateProjectDescription,
  validateProjectName,
  validateReferenceUrl,
  type ConfigurationField,
} from '@/domain/projects/rules';
import { validateStack } from '@/domain/projects/stack-validation';

/** Router state passed from the landing-page prompt to the wizard. Untrusted: parse before use. */
const wizardLocationStateSchema = z.object({ description: z.string().check(z.maxLength(PROJECT_LIMITS.descriptionMax)) });
export type WizardLocationState = z.infer<typeof wizardLocationStateSchema>;

export function parseWizardLocationState(value: unknown): WizardLocationState | null {
  const result = wizardLocationStateSchema.safeParse(value);
  return result.success ? result.data : null;
}

export const WIZARD_STEPS = [
  { id: 'idea', label: 'Project idea' },
  { id: 'stack', label: 'Technology' },
  { id: 'requirements', label: 'Requirements' },
  { id: 'review', label: 'Review' },
] as const;

export type WizardStepId = (typeof WIZARD_STEPS)[number]['id'];

/**
 * UI-only editing state. Unlike the domain `StackPreference`, the draft
 * remembers technology picks while "recommend" is selected, so toggling
 * modes does not lose them. Convert with `toConfiguration` before saving.
 */
const wizardDraftSchema = z.extend(projectConfigurationSchema, {
  stack: z.object({ mode: z.enum(['recommend', 'custom']), technologies: z.array(technologyIdSchema) }),
});
export type WizardDraft = z.infer<typeof wizardDraftSchema>;

const wizardStateSchema = z.object({
  step: z.int().check(z.gte(0), z.lte(WIZARD_STEPS.length - 1)),
  configuration: wizardDraftSchema,
});
export type WizardState = z.infer<typeof wizardStateSchema>;

/** Validates persisted draft state; anything malformed is discarded rather than rendered. */
export function parseWizardState(value: unknown): WizardState | null {
  const result = wizardStateSchema.safeParse(value);
  return result.success ? result.data : null;
}

export function emptyDraft(description = ''): WizardDraft {
  return {
    name: '',
    description,
    platform: 'website',
    referenceUrl: '',
    stack: { mode: 'recommend', technologies: [] },
    requirements: { features: [], custom: '' },
  };
}

export function draftFromConfiguration(configuration: ProjectConfiguration): WizardDraft {
  const { stack } = configuration;
  return {
    ...configuration,
    stack: { mode: stack.mode, technologies: stack.mode === 'custom' ? [...stack.technologies] : [] },
  };
}

function toStackPreference(draft: WizardDraft): StackPreference {
  return draft.stack.mode === 'custom'
    ? { mode: 'custom', technologies: draft.stack.technologies }
    : { mode: 'recommend' };
}

/** The domain configuration this draft would save, normalised. */
export function toConfiguration(draft: WizardDraft): ProjectConfiguration {
  return normalizeConfiguration({ ...draft, stack: toStackPreference(draft) });
}

export type WizardAction =
  | { type: 'update'; patch: Partial<Pick<WizardDraft, 'name' | 'description' | 'platform' | 'referenceUrl'>> }
  | { type: 'set-stack-mode'; mode: StackMode }
  | { type: 'toggle-technology'; id: TechnologyId }
  | { type: 'toggle-requirement'; id: RequirementId }
  | { type: 'set-custom-requirements'; value: string }
  | { type: 'go-to'; step: number };

const toggle = <T>(list: readonly T[], item: T): T[] =>
  list.includes(item) ? list.filter((entry) => entry !== item) : [...list, item];

export function wizardReducer(state: WizardState, action: WizardAction): WizardState {
  const { configuration } = state;
  switch (action.type) {
    case 'update':
      return { ...state, configuration: { ...configuration, ...action.patch } };
    case 'set-stack-mode':
      return { ...state, configuration: { ...configuration, stack: { ...configuration.stack, mode: action.mode } } };
    case 'toggle-technology':
      return {
        ...state,
        configuration: {
          ...configuration,
          stack: { mode: 'custom', technologies: toggle(configuration.stack.technologies, action.id) },
        },
      };
    case 'toggle-requirement':
      return {
        ...state,
        configuration: {
          ...configuration,
          requirements: {
            ...configuration.requirements,
            features: toggle(configuration.requirements.features, action.id),
          },
        },
      };
    case 'set-custom-requirements':
      return {
        ...state,
        configuration: { ...configuration, requirements: { ...configuration.requirements, custom: action.value } },
      };
    case 'go-to':
      return { ...state, step: Math.min(Math.max(action.step, 0), WIZARD_STEPS.length - 1) };
  }
}

export interface StepValidation {
  fieldErrors: Partial<Record<ConfigurationField, string>>;
  stackErrors: string[];
  stackWarnings: string[];
}

/** Applies the shared domain rules to the fields owned by one wizard step. */
export function validateStep(step: WizardStepId, draft: WizardDraft): StepValidation {
  const fieldErrors: StepValidation['fieldErrors'] = {};
  const set = (field: ConfigurationField, message: string | undefined) => {
    if (message) fieldErrors[field] = message;
  };
  let stackErrors: string[] = [];
  let stackWarnings: string[] = [];

  if (step === 'idea') {
    set('name', validateProjectName(draft.name));
    set('description', validateProjectDescription(draft.description));
    set('referenceUrl', validateReferenceUrl(draft.referenceUrl));
  }
  if (step === 'stack') {
    ({ errors: stackErrors, warnings: stackWarnings } = validateStack(draft.platform, toStackPreference(draft)));
  }
  if (step === 'requirements') {
    set('custom', validateCustomRequirements(draft.requirements.custom));
  }
  return { fieldErrors, stackErrors, stackWarnings };
}

export function isStepValid(step: WizardStepId, draft: WizardDraft): boolean {
  const { fieldErrors, stackErrors } = validateStep(step, draft);
  return Object.keys(fieldErrors).length === 0 && stackErrors.length === 0;
}

/** Index of the first step that fails validation, or -1 if all pass. */
export function firstInvalidStep(draft: WizardDraft): number {
  return WIZARD_STEPS.findIndex((step) => !isStepValid(step.id, draft));
}
