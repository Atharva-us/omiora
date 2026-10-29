import { useId } from 'react';
import { Badge } from '@/components/ui/Badge';
import { TextAreaField } from '@/components/ui/Field';
import type { Question } from '@/domain/requirements/requirements';
import { cn } from '@/lib/cn';
import type { AnswerDraft } from './requirements-model';

interface QuestionCardProps {
  question: Question;
  draft: AnswerDraft | undefined;
  disabled: boolean;
  onChange: (draft: AnswerDraft) => void;
}

const choiceClass = (selected: boolean, disabled: boolean) =>
  cn(
    'flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors',
    selected ? 'border-cyan/60 bg-cyan/[0.07] text-ink' : 'border-line text-muted hover:text-ink',
    disabled && 'cursor-not-allowed opacity-60',
  );

/** One analyst question with the control its kind needs and an explicit "I don't know". */
export function QuestionCard({ question, draft, disabled, onChange }: QuestionCardProps) {
  const groupId = useId();
  const unknown = draft?.unknown ?? false;
  const value = draft?.value;
  const controlsDisabled = disabled || unknown;
  const set = (next: AnswerDraft['value']) => onChange({ value: next, unknown: false });

  let control;
  if (question.kind === 'free-text') {
    control = (
      <TextAreaField
        label="Your answer"
        rows={3}
        maxLength={2000}
        value={typeof value === 'string' ? value : ''}
        disabled={controlsDisabled}
        onChange={(event) => set(event.target.value)}
      />
    );
  } else {
    const multiple = question.kind === 'multiple-choice';
    const options: { label: string; value: string | boolean }[] =
      question.kind === 'yes-no'
        ? [
            { label: 'Yes', value: true },
            { label: 'No', value: false },
          ]
        : question.options.map((option) => ({ label: option, value: option }));
    const selected = (option: string | boolean) =>
      multiple ? Array.isArray(value) && value.includes(option as string) : value === option;
    const toggle = (option: string | boolean) => {
      if (!multiple) return set(option);
      const current = Array.isArray(value) ? value : [];
      set(current.includes(option as string) ? current.filter((v) => v !== option) : [...current, option as string]);
    };
    control = (
      <fieldset aria-describedby={`${groupId}-why`} className="space-y-1.5" disabled={controlsDisabled}>
        <legend className="sr-only">{question.prompt}</legend>
        {options.map((option) => (
          <label key={String(option.value)} className={choiceClass(selected(option.value), controlsDisabled)}>
            <input
              type={multiple ? 'checkbox' : 'radio'}
              name={groupId}
              checked={selected(option.value)}
              onChange={() => toggle(option.value)}
              className="accent-cyan"
            />
            {option.label}
          </label>
        ))}
      </fieldset>
    );
  }

  return (
    <li className="rounded-lg border border-line bg-surface p-4">
      <div className="flex flex-wrap items-start gap-2">
        <span className="font-mono text-xs text-faint">{question.key}</span>
        <p className="flex-1 text-sm font-medium text-ink">{question.prompt}</p>
        {question.blocking && <Badge tone="warning">Blocking</Badge>}
        {question.answer && <Badge tone={question.answer.unknown ? 'neutral' : 'success'}>{question.answer.unknown ? "Don't know" : 'Answered'}</Badge>}
      </div>
      <p id={`${groupId}-why`} className="mt-1 text-[0.8125rem] text-muted">
        {question.why}
      </p>
      <div className="mt-3">{control}</div>
      <label className="mt-3 inline-flex items-center gap-2 text-[0.8125rem] text-muted">
        <input
          type="checkbox"
          checked={unknown}
          disabled={disabled}
          onChange={(event) => onChange({ value: undefined, unknown: event.target.checked })}
          className="accent-cyan"
        />
        I don&apos;t know
      </label>
      {unknown && (
        <p className="mt-1 text-xs text-faint">
          Recorded as unknown, never as an answer. The analyst keeps it open or records a low-confidence assumption you can review.
        </p>
      )}
    </li>
  );
}
