import { useId, type ReactNode } from 'react';
import { Check } from 'lucide-react';
import { cn } from '@/lib/cn';

interface SelectableCardProps {
  type: 'radio' | 'checkbox';
  name: string;
  value: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  meta?: ReactNode;
  icon?: ReactNode;
  disabled?: boolean;
}

/**
 * A card that wraps a native radio/checkbox, so keyboard and screen-reader
 * behaviour come from the platform rather than custom ARIA.
 */
export function SelectableCard({
  type,
  name,
  value,
  checked,
  onChange,
  title,
  description,
  meta,
  icon,
  disabled,
}: SelectableCardProps) {
  const id = useId();
  const titleId = `${id}-title`;
  const descriptionId = `${id}-description`;
  return (
    <label
      className={cn(
        'group relative flex cursor-pointer gap-3 rounded-lg border p-4 transition-colors',
        'has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-cyan',
        checked ? 'border-cyan/60 bg-cyan/[0.05]' : 'border-line bg-surface hover:border-[#33415a]',
        disabled && 'cursor-not-allowed opacity-50',
      )}
    >
      <input
        type={type}
        name={name}
        value={value}
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        className="sr-only"
      />
      {icon && (
        <span
          aria-hidden="true"
          className={cn(
            'flex size-9 shrink-0 items-center justify-center rounded-md border',
            checked ? 'border-cyan/40 text-cyan' : 'border-line text-muted',
          )}
        >
          {icon}
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2 text-sm font-medium text-ink">
          <span id={titleId}>{title}</span>
          {meta}
        </span>
        {description && (
          <span id={descriptionId} className="mt-1 block text-[0.8125rem] leading-relaxed text-muted">
            {description}
          </span>
        )}
      </span>
      <span
        aria-hidden="true"
        className={cn(
          'flex size-5 shrink-0 items-center justify-center border transition-colors',
          type === 'radio' ? 'rounded-full' : 'rounded',
          checked ? 'border-cyan bg-cyan text-obsidian' : 'border-line',
        )}
      >
        {checked && <Check className="size-3.5" strokeWidth={3} />}
      </span>
    </label>
  );
}
