import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AppError } from '@/domain/errors';
import { createTestServices } from '@/test/render-app';
import { ServicesProvider } from '../providers/ServicesProvider';
import { RouteErrorPage } from './RouteErrorPage';

function renderThrowing(error: unknown) {
  const services = createTestServices();
  function Broken(): never {
    throw error;
  }
  const router = createMemoryRouter([{ path: '/', element: <Broken />, errorElement: <RouteErrorPage /> }]);
  render(
    <ServicesProvider services={services}>
      <RouterProvider router={router} />
    </ServicesProvider>,
  );
  return services;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('RouteErrorPage', () => {
  it('replaces unexpected errors with a safe message and logs them', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const services = renderThrowing(new TypeError("Cannot read properties of undefined (reading 'secret')"));
    expect(screen.getByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Your saved projects are not affected.');
    expect(screen.getByRole('alert')).not.toHaveTextContent('reading');
    expect(screen.getByRole('button', { name: 'Reload page' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Go home' })).toHaveAttribute('href', '/');
    expect(services.memoryLogger.entries).toContainEqual(expect.objectContaining({ level: 'error', event: 'route.render-failed' }));
  });

  it('shows the message of an expected AppError', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    renderThrowing(new AppError('storage-unavailable', 'Browser storage is unavailable.'));
    expect(screen.getByRole('alert')).toHaveTextContent('Browser storage is unavailable.');
  });
});
