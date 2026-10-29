import type { ReactNode } from 'react';
import { CircleAlert, CircleCheck, Info, TriangleAlert, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';

type NoticeTone = 'info' | 'success' | 'warning' | 'danger';

const toneStyles: Record<NoticeTone, { className: string; icon: LucideIcon }> = {
  info: { className: 'border-azure/30 bg-azure/[0.07] text-[#b9d0ff]', icon: Info },
  success: { className: 'border-success/30 bg-success/[0.07] text-[#a7f3d0]', icon: CircleCheck },
  warning: { className: 'border-warning/30 bg-warning/[0.07] text-[#fde68a]', icon: TriangleAlert },
  danger: { className: 'border-danger/30 bg-danger/[0.08] text-[#fecaca]', icon: CircleAlert },
};

interface NoticeProps {
  tone?: NoticeTone;
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
  /** Use "alert" for errors that appear in response to an action. */
  role?: 'status' | 'alert';
  action?: ReactNode;
}

export function Notice({ tone = 'info', title, children, className, role, action }: NoticeProps) {
  const { className: toneClass, icon: Icon } = toneStyles[tone];
  return (
    <div role={role} className={cn('flex gap-3 rounded-lg border px-4 py-3 text-sm', toneClass, className)}>
      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 flex-1 space-y-1">
        {title && <p className="font-medium text-ink">{title}</p>}
        {children && <div className="leading-relaxed opacity-90">{children}</div>}
      </div>
      {action && <div className="shrink-0 self-center">{action}</div>}
    </div>
  );
}
