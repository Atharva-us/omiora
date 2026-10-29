import { LoaderCircle } from 'lucide-react';
import { cn } from '@/lib/cn';

export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <>
      <LoaderCircle aria-hidden="true" className={cn('size-4 animate-spin', className)} />
      {label && <span className="sr-only">{label}</span>}
    </>
  );
}

export function LoadingBlock({ label = 'Loading' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-16 text-sm text-muted">
      <Spinner />
      {label}…
    </div>
  );
}
