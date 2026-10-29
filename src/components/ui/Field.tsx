import { useId, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from 'react';
import { CircleAlert } from 'lucide-react';
import { cn } from '@/lib/cn';

const controlBase =
  'w-full rounded-md border bg-surface text-sm text-ink placeholder:text-faint transition-colors ' +
  'focus:outline-none focus:ring-2 focus:ring-cyan/40 focus:border-cyan/70 disabled:opacity-60';

interface FieldShellProps {
  id: string;
  label: ReactNode;
  hint?: ReactNode;
  error?: string | undefined;
  optional?: boolean;
  trailing?: ReactNode;
  children: ReactNode;
}

function FieldShell({ id, label, hint, error, optional, trailing, children }: FieldShellProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium text-ink">
          {label}
          {optional && <span className="ml-1.5 font-normal text-faint">(optional)</span>}
        </label>
        {trailing}
      </div>
      {children}
      {error ? (
        <p id={`${id}-error`} className="flex items-center gap-1.5 text-[0.8125rem] text-danger">
          <CircleAlert aria-hidden="true" className="size-3.5 shrink-0" />
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="text-[0.8125rem] text-faint">
            {hint}
          </p>
        )
      )}
    </div>
  );
}

function describedBy(id: string, error: string | undefined, hint: ReactNode) {
  if (error) return `${id}-error`;
  if (hint) return `${id}-hint`;
  return undefined;
}

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  label: ReactNode;
  hint?: ReactNode;
  error?: string | undefined;
  optional?: boolean;
  trailing?: ReactNode;
  /** Rendered inside the input frame, after the input (e.g. a visibility toggle). */
  adornment?: ReactNode;
}

export function TextField({ label, hint, error, optional, trailing, adornment, className, ...props }: TextFieldProps) {
  const id = useId();
  return (
    <FieldShell id={id} label={label} hint={hint} error={error} optional={optional} trailing={trailing}>
      <div className="relative">
        <input
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(id, error, hint)}
          className={cn(
            controlBase,
            'h-10 px-3',
            adornment ? 'pr-11' : undefined,
            error ? 'border-danger/70' : 'border-line',
            className,
          )}
          {...props}
        />
        {adornment && <div className="absolute inset-y-0 right-1 flex items-center">{adornment}</div>}
      </div>
    </FieldShell>
  );
}

interface TextAreaFieldProps extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'id'> {
  label: ReactNode;
  hint?: ReactNode;
  error?: string | undefined;
  optional?: boolean;
  trailing?: ReactNode;
}

export function TextAreaField({ label, hint, error, optional, trailing, className, ...props }: TextAreaFieldProps) {
  const id = useId();
  return (
    <FieldShell id={id} label={label} hint={hint} error={error} optional={optional} trailing={trailing}>
      <textarea
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, error, hint)}
        className={cn(
          controlBase,
          'min-h-28 resize-y px-3 py-2.5 leading-relaxed',
          error ? 'border-danger/70' : 'border-line',
          className,
        )}
        {...props}
      />
    </FieldShell>
  );
}

export function CharacterCount({ value, max }: { value: string; max: number }) {
  const over = value.length > max;
  return (
    <span className={cn('font-mono text-xs tabular-nums', over ? 'text-danger' : 'text-faint')} aria-live="polite">
      {value.length}/{max}
    </span>
  );
}
