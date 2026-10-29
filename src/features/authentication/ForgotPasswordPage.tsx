import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/Field';
import { Notice } from '@/components/ui/Notice';
import { useServices } from '@/hooks/use-services';
import { isValidEmail } from '@/domain/authentication/types';
import { useErrorReporter } from '@/hooks/use-error-reporter';
import { AuthCard } from './AuthCard';

export function ForgotPasswordPage() {
  const { auth } = useServices();
  const reportError = useErrorReporter();
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | undefined>();
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError(null);
    if (!email.trim()) return setError('Enter your email address.');
    if (!isValidEmail(email)) return setError('Enter a valid email address.');
    setError(undefined);
    setSubmitting(true);
    try {
      await auth.requestPasswordReset(email.trim());
      setSent(true);
    } catch (cause) {
      setFormError(reportError('auth.request-failed', cause));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthCard
      title="Reset your password"
      subtitle="Enter your account email and we will send reset instructions."
      providerConfigured={auth.isConfigured}
      footer={
        <Link to="/sign-in" className="font-medium text-cyan hover:underline">
          Back to sign in
        </Link>
      }
    >
      {sent ? (
        <Notice tone="success" role="status" title="Check your inbox">
          If an account exists for {email.trim()}, reset instructions are on their way.
        </Notice>
      ) : (
        <form onSubmit={onSubmit} noValidate className="space-y-5">
          {formError && (
            <Notice tone="danger" role="alert" title="Reset not sent">
              {formError}
            </Notice>
          )}
          <TextField
            label="Email"
            type="email"
            name="email"
            autoComplete="email"
            value={email}
            error={error}
            onChange={(event) => setEmail(event.target.value)}
          />
          <Button type="submit" className="w-full" loading={submitting}>
            Send reset instructions
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
