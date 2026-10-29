import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/Field';
import { Notice } from '@/components/ui/Notice';
import { useServices } from '@/hooks/use-services';
import { useSession } from '@/hooks/use-session';
import { isValidEmail } from '@/domain/authentication/types';
import { useErrorReporter } from '@/hooks/use-error-reporter';
import { AuthCard } from './AuthCard';
import { PasswordField } from './PasswordField';

interface Errors {
  email?: string;
  password?: string;
}

export function SignInPage() {
  const { auth } = useServices();
  const reportError = useErrorReporter();
  const navigate = useNavigate();
  const session = useSession();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Errors>({});
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const validate = (): Errors => {
    const next: Errors = {};
    if (!email.trim()) next.email = 'Enter your email address.';
    else if (!isValidEmail(email)) next.email = 'Enter a valid email address.';
    if (!password) next.password = 'Enter your password.';
    return next;
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const nextErrors = validate();
    setErrors(nextErrors);
    setFormError(null);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    try {
      await auth.signIn({ email: email.trim(), password });
      await session.refresh();
      navigate('/projects');
    } catch (error) {
      setFormError(reportError('auth.request-failed', error));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthCard
      title="Sign in to Omniora"
      subtitle="Welcome back. Continue building."
      providerConfigured={auth.isConfigured}
      footer={
        <>
          New to Omniora?{' '}
          <Link to="/register" className="font-medium text-cyan hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-5">
        {formError && (
          <Notice tone="danger" role="alert" title="Sign-in failed">
            {formError}
          </Notice>
        )}
        <TextField
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          value={email}
          error={errors.email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <PasswordField
          name="password"
          autoComplete="current-password"
          value={password}
          error={errors.password}
          onChange={(event) => setPassword(event.target.value)}
          trailing={
            <Link to="/forgot-password" className="text-[0.8125rem] text-muted hover:text-ink">
              Forgot password?
            </Link>
          }
        />
        <Button type="submit" className="w-full" loading={submitting}>
          Sign in
        </Button>
      </form>
    </AuthCard>
  );
}
