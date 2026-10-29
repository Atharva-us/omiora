import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
export type BadgeTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger';

const tones: Record<BadgeTone, string> = {
  neutral: 'border-line text-muted bg-elevated',
  info: 'border-azure/35 text-[#8db4ff] bg-azure/10',
  success: 'border-success/35 text-success bg-success/10',
  warning: 'border-warning/35 text-warning bg-warning/10',
  danger: 'border-danger/35 text-danger bg-danger/10',
};

interface BadgeProps {
  tone?: BadgeTone;
  children: ReactNode;
  className?: string;
  dot?: boolean;
}

export function Badge({ tone = 'neutral', children, className, dot = false }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        tones[tone],
        className,
      )}
    >
      {dot && <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}
