import { Button, ButtonLink } from '@/components/ui/Button';
import { Notice } from '@/components/ui/Notice';
import type { AppErrorCode } from '@/domain/errors';

interface LoadErrorNoticeProps {
  title: string;
  message: string;
  code: AppErrorCode | undefined;
  onRetry: () => void;
  className?: string;
}

/** A failed load with the recovery that fits the error: sign in when unauthenticated, otherwise retry. */
export function LoadErrorNotice({ title, message, code, onRetry, className }: LoadErrorNoticeProps) {
  const action =
    code === 'unauthenticated' ? (
      <ButtonLink to="/sign-in" size="sm">
        Sign in
      </ButtonLink>
    ) : (
      <Button size="sm" variant="secondary" onClick={onRetry}>
        Retry
      </Button>
    );
  return (
    <Notice tone={code === 'unauthenticated' ? 'info' : 'danger'} role="alert" title={title} action={action} className={className}>
      {message}
    </Notice>
  );
}
