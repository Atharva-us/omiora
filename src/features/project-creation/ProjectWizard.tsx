import { useEffect, useReducer, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Check } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Notice } from '@/components/ui/Notice';
import type { ProjectConfiguration } from '@/domain/projects/project';
import { useErrorReporter } from '@/hooks/use-error-reporter';
import { IdeaStep } from './steps/IdeaStep';
import { RequirementsStep } from './steps/RequirementsStep';
import { ReviewStep } from './steps/ReviewStep';
import { StackStep } from './steps/StackStep';
import { WizardStepper } from './WizardStepper';
import {
  firstInvalidStep,
  toConfiguration,
  validateStep,
  WIZARD_STEPS,
  wizardReducer,
  type WizardState,
} from './wizard-model';

const STEP_COPY = [
  { title: 'Describe your project', description: 'Start with the idea. You can refine every answer before saving.' },
  { title: 'Choose your technology', description: 'Pick a stack you prefer, or ask Omniora to recommend one.' },
  { title: 'Define requirements', description: 'Tell us which capabilities the first version needs.' },
  { title: 'Review your project', description: 'Check everything before you save the configuration.' },
] as const;

interface ProjectWizardProps {
  initialState: WizardState;
  mode: 'create' | 'edit';
  /** Called after every change, e.g. to persist a draft. The wizard itself knows nothing about storage. */
  onStateChange?: (state: WizardState) => void;
  onComplete: (configuration: ProjectConfiguration) => Promise<void>;
}

export function ProjectWizard({ initialState, mode, onStateChange, onComplete }: ProjectWizardProps) {
  const [state, dispatch] = useReducer(wizardReducer, initialState);
  const reportError = useErrorReporter();
  const [attempted, setAttempted] = useState<ReadonlySet<number>>(() => new Set());
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const isFirstRender = useRef(true);

  const { step, configuration } = state;
  const stepId = WIZARD_STEPS[step]?.id ?? 'idea';
  const validation = validateStep(stepId, configuration);
  const stepIsValid = Object.keys(validation.fieldErrors).length === 0 && validation.stackErrors.length === 0;
  const showErrors = attempted.has(step);
  const firstInvalid = firstInvalidStep(configuration);
  const reachable = firstInvalid === -1 ? WIZARD_STEPS.length - 1 : firstInvalid;

  useEffect(() => {
    onStateChange?.(state);
  }, [onStateChange, state]);

  // Move focus to the step heading after navigation so screen-reader and
  // keyboard users land at the start of the new content.
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    headingRef.current?.focus();
  }, [step]);

  const goTo = (target: number) => dispatch({ type: 'go-to', step: target });

  const next = () => {
    if (!stepIsValid) {
      setAttempted((previous) => new Set(previous).add(step));
      return;
    }
    goTo(step + 1);
  };

  const requestCompletion = () => {
    if (firstInvalid !== -1) {
      setAttempted((previous) => new Set(previous).add(firstInvalid));
      goTo(firstInvalid);
      return;
    }
    setSubmitError(null);
    setConfirmOpen(true);
  };

  const confirm = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await onComplete(toConfiguration(configuration));
    } catch (error) {
      setSubmitError(reportError('wizard.save-failed', error, 'The project could not be saved. Please try again.'));
      setSubmitting(false);
      setConfirmOpen(false);
    }
  };

  const copy = STEP_COPY[step] ?? STEP_COPY[0];
  const isReview = stepId === 'review';

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-12">
      <aside className="lg:sticky lg:top-24 lg:self-start">
        <WizardStepper current={step} reachable={reachable} onSelect={goTo} />
      </aside>

      <form
        noValidate
        aria-labelledby="wizard-step-heading"
        onSubmit={(event) => {
          event.preventDefault();
          if (isReview) requestCompletion();
          else next();
        }}
        className="min-w-0"
      >
        <div className="mb-8">
          <p className="font-mono text-xs text-faint">
            {String(step + 1).padStart(2, '0')} / {String(WIZARD_STEPS.length).padStart(2, '0')}
          </p>
          <h2
            id="wizard-step-heading"
            ref={headingRef}
            tabIndex={-1}
            className="mt-2 text-2xl font-semibold tracking-[-0.02em] text-ink focus:outline-none"
          >
            {copy.title}
          </h2>
          <p className="mt-1.5 text-sm text-muted">{copy.description}</p>
        </div>

        {showErrors && !stepIsValid && Object.keys(validation.fieldErrors).length > 0 && (
          <Notice tone="danger" role="alert" className="mb-6">
            Some answers need attention before you can continue.
          </Notice>
        )}

        {stepId === 'idea' && (
          <IdeaStep configuration={configuration} dispatch={dispatch} validation={showErrors ? validation : null} />
        )}
        {stepId === 'stack' && (
          <StackStep
            configuration={configuration}
            dispatch={dispatch}
            validation={validation}
            showAllErrors={showErrors}
          />
        )}
        {stepId === 'requirements' && (
          <RequirementsStep
            configuration={configuration}
            dispatch={dispatch}
            validation={showErrors ? validation : null}
          />
        )}
        {isReview && (
          <>
            <ReviewStep configuration={toConfiguration(configuration)} onEdit={goTo} />
            <Notice tone="info" className="mt-6" title="What happens next">
              {mode === 'create'
                ? 'Creating the project saves this configuration and opens its workspace. Code generation is not connected yet, so no code will be generated.'
                : 'Saving updates the configuration for this project. No generation run is started.'}
            </Notice>
          </>
        )}

        {submitError && (
          <Notice tone="danger" role="alert" className="mt-6" title="The project was not saved">
            {submitError}
          </Notice>
        )}

        <div className="mt-10 flex items-center justify-between gap-3 border-t border-line-soft pt-6">
          <Button variant="secondary" onClick={() => goTo(step - 1)} disabled={step === 0}>
            <ArrowLeft aria-hidden="true" />
            Back
          </Button>
          <Button type="submit">
            {isReview ? (
              <>
                <Check aria-hidden="true" />
                {mode === 'create' ? 'Create project' : 'Save changes'}
              </>
            ) : (
              <>
                Next
                <ArrowRight aria-hidden="true" />
              </>
            )}
          </Button>
        </div>
      </form>

      <Modal
        open={confirmOpen}
        onClose={() => !submitting && setConfirmOpen(false)}
        title={mode === 'create' ? 'Create this project?' : 'Save these changes?'}
        description={
          mode === 'create'
            ? `"${configuration.name.trim()}" will be saved in this browser and opened in a new workspace.`
            : 'The project configuration will be updated.'
        }
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmOpen(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={confirm} loading={submitting} data-autofocus>
              {mode === 'create' ? 'Create project' : 'Save changes'}
            </Button>
          </>
        }
      >
        <ul className="space-y-2 text-sm text-muted">
          <li>• Your configuration is stored locally on this device (demo storage). It is not sent to a server.</li>
          <li>• The AI generation engine is not connected yet, so no code, builds, or tests will run.</li>
          <li>• You can edit the configuration from the workspace at any time.</li>
        </ul>
      </Modal>
    </div>
  );
}
