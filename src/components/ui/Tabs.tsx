import { useRef, type KeyboardEvent, type ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';

export interface TabItem<T extends string> {
  id: T;
  label: string;
  icon?: LucideIcon;
}

interface TabsProps<T extends string> {
  idPrefix: string;
  label: string;
  items: readonly TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
}

/** WAI-ARIA tabs with roving tabindex and arrow/Home/End keyboard support. */
export function Tabs<T extends string>({ idPrefix, label, items, value, onChange, className }: TabsProps<T>) {
  const listRef = useRef<HTMLDivElement>(null);

  const focusTab = (index: number) => {
    const item = items[(index + items.length) % items.length];
    if (!item) return;
    onChange(item.id);
    listRef.current?.querySelector<HTMLButtonElement>(`#${idPrefix}-tab-${item.id}`)?.focus();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = items.findIndex((item) => item.id === value);
    const keyActions: Record<string, () => void> = {
      ArrowRight: () => focusTab(index + 1),
      ArrowLeft: () => focusTab(index - 1),
      Home: () => focusTab(0),
      End: () => focusTab(items.length - 1),
    };
    const action = keyActions[event.key];
    if (action) {
      event.preventDefault();
      action();
    }
  };

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={cn('scrollbar-thin flex items-center gap-1 overflow-x-auto', className)}
    >
      {items.map(({ id, label: itemLabel, icon: Icon }) => {
        const selected = id === value;
        return (
          <button
            key={id}
            id={`${idPrefix}-tab-${id}`}
            type="button"
            role="tab"
            aria-selected={selected}
            // Only the selected panel is rendered, so only it can be referenced.
            aria-controls={selected ? `${idPrefix}-panel-${id}` : undefined}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(id)}
            className={cn(
              'relative inline-flex h-9 shrink-0 items-center gap-2 rounded-md px-3 text-sm font-medium transition-colors',
              selected ? 'bg-elevated text-ink' : 'text-muted hover:text-ink',
            )}
          >
            {Icon && <Icon aria-hidden="true" className={cn('size-4', selected && 'text-cyan')} />}
            {itemLabel}
          </button>
        );
      })}
    </div>
  );
}

interface TabPanelProps {
  idPrefix: string;
  id: string;
  children: ReactNode;
  className?: string;
}

export function TabPanel({ idPrefix, id, children, className }: TabPanelProps) {
  return (
    <div
      id={`${idPrefix}-panel-${id}`}
      role="tabpanel"
      aria-labelledby={`${idPrefix}-tab-${id}`}
      tabIndex={0}
      className={cn('focus-visible:outline-offset-[-2px]', className)}
    >
      {children}
    </div>
  );
}
