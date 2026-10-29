import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useServices } from '@/hooks/use-services';
import { ProjectWizard } from './ProjectWizard';
import { clearWizardDraft, loadWizardDraft, saveWizardDraft } from './wizard-draft';
import { emptyDraft, parseWizardLocationState, type WizardState } from './wizard-model';

export function NewProjectPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { projects, uiState, logger } = useServices();
  const [initialState, setInitialState] = useState<WizardState>(() => {
    // A description handed over from the landing-page prompt starts a fresh draft.
    const handedOver = parseWizardLocationState(location.state);
    if (handedOver) return { step: 0, configuration: emptyDraft(handedOver.description) };
    return loadWizardDraft(uiState, logger) ?? { step: 0, configuration: emptyDraft() };
  });
  const [wizardKey, setWizardKey] = useState(0);

  // Consume the router state once so a reload restores the saved draft
  // instead of re-applying the original prompt.
  useEffect(() => {
    if (location.state) navigate(location.pathname, { replace: true, state: null });
  }, [location.state, location.pathname, navigate]);

  const persistDraft = useCallback((state: WizardState) => saveWizardDraft(uiState, logger, state), [uiState, logger]);

  const startOver = () => {
    clearWizardDraft(uiState, logger);
    setInitialState({ step: 0, configuration: emptyDraft() });
    setWizardKey((key) => key + 1);
  };

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
      <div className="mb-10 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-mono text-xs tracking-[0.16em] text-cyan">NEW PROJECT</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-[-0.025em]">Set up your project</h1>
        </div>
        <Button variant="ghost" size="sm" onClick={startOver} className="self-start sm:self-auto">
          <RotateCcw aria-hidden="true" />
          Start over
        </Button>
      </div>

      <ProjectWizard
        key={wizardKey}
        mode="create"
        initialState={initialState}
        onStateChange={persistDraft}
        onComplete={async (configuration) => {
          const project = await projects.createProject(configuration);
          clearWizardDraft(uiState, logger);
          navigate(`/projects/${project.id}`, { replace: true });
        }}
      />
    </div>
  );
}
