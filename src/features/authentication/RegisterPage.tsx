import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/Field';
import { Notice } from '@/components/ui/Notice';
import { useServices } from '@/hooks/use-services';
import { useSession } from '@/hooks/use-session';
import { isValidEmail, PASSWORD_MIN_LENGTH } from '@/domain/authentication/types';
import { useErrorReporter } from '@/hooks/use-error-reporter';
import { AuthCard } from './AuthCard';
import { PasswordField } from './PasswordField';


interface Errors {
  name?: string;
  email?: string;
  password?: string;
}

export function RegisterPage() {
  const { auth } = useServices();
  const reportError = useErrorReporter();
  const navigate = useNavigate();
  const session = useSession();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Errors>({});
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const validate = (): Errors => {
    const next: Errors = {};
    if (!name.trim()) next.name = 'Enter your name.';
    if (!email.trim()) next.email = 'Enter your email address.';
    else if (!isValidEmail(email)) next.email = 'Enter a valid email address.';
    if (!password) next.password = 'Create a password.';
    else if (password.length < PASSWORD_MIN_LENGTH)
      next.password = `Use at least ${PASSWORD_MIN_LENGTH} characters.`;
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
      await auth.register({ name: name.trim(), email: email.trim(), password });
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
      title="Create your account"
      subtitle="Start turning ideas into software."
      providerConfigured={auth.isConfigured}
      footer={
        <>
          Already have an account?{' '}
          <Link to="/sign-in" className="font-medium text-cyan hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-5">
        {formError && (
          <Notice tone="danger" role="alert" title="Account not created">
            {formError}
          </Notice>
        )}
        <TextField
          label="Name"
          name="name"
          autoComplete="name"
          value={name}
          error={errors.name}
          onChange={(event) => setName(event.target.value)}
        />
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
          autoComplete="new-password"
          value={password}
          error={errors.password}
          hint={`At least ${PASSWORD_MIN_LENGTH} characters.`}
          onChange={(event) => setPassword(event.target.value)}
        />
        <Button type="submit" className="w-full" loading={submitting}>
          Create account
        </Button>
      </form>
    </AuthCard>
  );
}
