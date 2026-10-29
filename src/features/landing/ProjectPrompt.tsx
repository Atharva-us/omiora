import { useId, useState, type FormEvent, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowUp, CircleAlert, CornerDownLeft } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/cn';
import { PROJECT_LIMITS } from '@/domain/projects/rules';
import { EXAMPLE_PROMPTS } from './content';

const DESCRIPTION_MAX_LENGTH = PROJECT_LIMITS.descriptionMax;

export function ProjectPrompt() {
  const navigate = useNavigate();
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const inputId = useId();
  const errorId = `${inputId}-error`;
  const tooLong = value.length > DESCRIPTION_MAX_LENGTH;

  const submit = () => {
    const description = value.trim();
    if (!description) {
      setError('Describe what you want to build before continuing.');
      return;
    }
    if (tooLong) {
      setError(`Keep the description under ${DESCRIPTION_MAX_LENGTH} characters.`);
      return;
    }
    // The wizard validates this router state as untrusted input (see parseWizardLocationState).
    navigate('/new', { state: { description } });
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form onSubmit={onSubmit} noValidate aria-label="Start a project" className="w-full">
      <div
        className={cn(
          'rounded-xl border bg-surface/90 shadow-panel transition-colors focus-within:border-cyan/60',
          error ? 'border-danger/60' : 'border-line',
        )}
      >
        <label htmlFor={inputId} className="sr-only">
          Describe the software you want to build
        </label>
        <textarea
          id={inputId}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            if (error) setError(null);
          }}
          onKeyDown={onKeyDown}
          rows={4}
          placeholder="Describe the software you want to build..."
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          className="block w-full resize-none rounded-t-xl bg-transparent px-4 pt-4 pb-2 text-[0.9375rem] leading-relaxed text-ink placeholder:text-faint focus:outline-none"
        />
        <div className="flex items-center justify-between gap-3 px-3 pb-3">
          <div className="flex items-center gap-3 pl-1 text-xs text-faint">
            <span className={cn('font-mono tabular-nums', tooLong && 'text-danger')}>
              {value.length}/{DESCRIPTION_MAX_LENGTH}
            </span>
            <span className="hidden items-center gap-1 sm:inline-flex">
              <kbd className="rounded border border-line px-1 font-mono">Ctrl</kbd>
              <CornerDownLeft aria-hidden="true" className="size-3" />
              <span className="sr-only">Enter</span>
              to continue
            </span>
          </div>
          <Button type="submit" size="sm" aria-label="Continue to project setup">
            Continue
            <ArrowUp aria-hidden="true" className="rotate-45" />
          </Button>
        </div>
      </div>

      {error && (
        <p id={errorId} role="alert" className="mt-2 flex items-center gap-1.5 text-sm text-danger">
          <CircleAlert aria-hidden="true" className="size-4" />
          {error}
        </p>
      )}

      <div className="mt-4">
        <p className="mb-2 text-xs text-faint">Try an example</p>
        <ul className="flex flex-wrap gap-2">
          {EXAMPLE_PROMPTS.map((example) => (
            <li key={example}>
              <button
                type="button"
                onClick={() => {
                  setValue(example);
                  setError(null);
                  document.getElementById(inputId)?.focus();
                }}
                className="rounded-md border border-line bg-surface px-2.5 py-1.5 text-left text-[0.8125rem] text-muted transition-colors hover:border-cyan/50 hover:text-ink"
              >
                {example}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </form>
  );
}
