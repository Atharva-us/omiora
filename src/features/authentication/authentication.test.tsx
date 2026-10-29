import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '@/test/render-app';

describe('Authentication screens', () => {
  it('validates sign-in fields before calling the provider', async () => {
    const { user } = renderApp({ route: '/sign-in' });
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(screen.getByText('Enter your email address.')).toBeInTheDocument();
    expect(screen.getByText('Enter your password.')).toBeInTheDocument();

    await user.type(screen.getByLabelText('Email'), 'not-an-email');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument();
  });

  it('reports that no provider is configured instead of faking a session', async () => {
    const { user, router } = renderApp({ route: '/sign-in' });
    await user.type(screen.getByLabelText('Email'), 'dev@example.com');
    await user.type(screen.getByLabelText('Password'), 'correct horse');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('No authentication provider is connected');
    expect(router.state.location.pathname).toBe('/sign-in');
  });

  it('toggles password visibility', async () => {
    const { user } = renderApp({ route: '/sign-in' });
    const password = screen.getByLabelText('Password');
    expect(password).toHaveAttribute('type', 'password');
    await user.click(screen.getByRole('button', { name: 'Show password' }));
    expect(password).toHaveAttribute('type', 'text');
    await user.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(password).toHaveAttribute('type', 'password');
  });

  it('enforces a minimum password length on registration', async () => {
    const { user } = renderApp({ route: '/register' });
    await user.type(screen.getByLabelText('Name'), 'Ada');
    await user.type(screen.getByLabelText('Email'), 'ada@example.com');
    await user.type(screen.getByLabelText('Password'), 'short');
    await user.click(screen.getByRole('button', { name: 'Create account' }));
    expect(screen.getByText('Use at least 8 characters.')).toBeInTheDocument();
  });

  it('links between sign-in, registration, and password reset', async () => {
    const { user, router } = renderApp({ route: '/sign-in' });
    await user.click(screen.getByRole('link', { name: 'Forgot password?' }));
    expect(router.state.location.pathname).toBe('/forgot-password');
    await user.click(screen.getByRole('link', { name: 'Back to sign in' }));
    await user.click(screen.getByRole('link', { name: 'Create an account' }));
    expect(router.state.location.pathname).toBe('/register');
  });

  it('never writes credentials to web storage', async () => {
    const { user } = renderApp({ route: '/sign-in' });
    await user.type(screen.getByLabelText('Email'), 'dev@example.com');
    await user.type(screen.getByLabelText('Password'), 'super-secret-value');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    await screen.findByRole('alert');
    const stored = JSON.stringify({ ...window.localStorage }) + JSON.stringify({ ...window.sessionStorage });
    expect(stored).not.toContain('super-secret-value');
  });
});
