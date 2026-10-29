import { Check } from 'lucide-react';
import { cn } from '@/lib/cn';
import { WIZARD_STEPS } from './wizard-model';

interface WizardStepperProps {
  current: number;
  /** Highest step index the user may jump to. */
  reachable: number;
  onSelect: (step: number) => void;
}

export function WizardStepper({ current, reachable, onSelect }: WizardStepperProps) {
  const progress = ((current + 1) / WIZARD_STEPS.length) * 100;
  return (
    <nav aria-label="Project setup progress">
      {/* Compact progress for small screens */}
      <div className="lg:hidden">
        <div className="flex items-center justify-between text-xs">
          <span className="font-medium text-ink">{WIZARD_STEPS[current]?.label}</span>
          <span className="font-mono text-faint">
            Step {current + 1} of {WIZARD_STEPS.length}
          </span>
        </div>
        <div
          className="mt-2 h-1 overflow-hidden rounded-full bg-elevated"
          role="progressbar"
          aria-label="Setup progress"
          aria-valuemin={1}
          aria-valuemax={WIZARD_STEPS.length}
          aria-valuenow={current + 1}
        >
          <div className="h-full rounded-full bg-cyan transition-[width] duration-300" style={{ width: `${progress}%` }} />
        </div>
      </div>

      <ol className="hidden flex-col gap-1 lg:flex">
        {WIZARD_STEPS.map((step, index) => {
          const isCurrent = index === current;
          const isComplete = index < current;
          const isReachable = index <= reachable;
          return (
            <li key={step.id}>
              <button
                type="button"
                onClick={() => onSelect(index)}
                disabled={!isReachable}
                aria-current={isCurrent ? 'step' : undefined}
                className={cn(
                  'flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm transition-colors',
                  isCurrent ? 'bg-elevated text-ink' : 'text-muted hover:text-ink',
                  !isReachable && 'cursor-not-allowed opacity-50 hover:text-muted',
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    'flex size-6 shrink-0 items-center justify-center rounded-full border font-mono text-xs',
                    isCurrent && 'border-cyan text-cyan',
                    isComplete && 'border-cyan bg-cyan text-obsidian',
                    !isCurrent && !isComplete && 'border-line',
                  )}
                >
                  {isComplete ? <Check className="size-3.5" strokeWidth={3} /> : index + 1}
                </span>
                {step.label}
                {isComplete && <span className="sr-only">(completed)</span>}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
