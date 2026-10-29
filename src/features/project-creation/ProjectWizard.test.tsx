import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AppError } from '@/domain/errors';
import { createTestServices, renderApp } from '@/test/render-app';

const DESCRIPTION = 'A premium fashion storefront with curated collections.';

async function completeIdeaStep(user: ReturnType<typeof renderApp>['user']) {
  await user.type(screen.getByLabelText('Project name'), 'Atelier');
  await user.type(screen.getByLabelText(/Project description/), DESCRIPTION);
  await user.click(screen.getByRole('button', { name: /next/i }));
}

describe('Landing prompt → wizard', () => {
  it('validates an empty prompt instead of navigating', async () => {
    const { user, router } = renderApp();
    await user.click(screen.getByRole('button', { name: 'Continue to project setup' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Describe what you want to build');
    expect(router.state.location.pathname).toBe('/');
  });

  it('carries the prompt into the wizard description', async () => {
    const { user, router } = renderApp();
    await user.click(screen.getByRole('button', { name: 'Create a SaaS analytics dashboard' }));
    await user.click(screen.getByRole('button', { name: 'Continue to project setup' }));
    expect(router.state.location.pathname).toBe('/new');
    expect(await screen.findByLabelText(/Project description/)).toHaveValue('Create a SaaS analytics dashboard');
  });
});

describe('Project creation wizard', () => {
  it('blocks progress until step 1 is valid', async () => {
    const { user } = renderApp({ route: '/new' });
    await user.click(screen.getByRole('button', { name: /next/i }));
    expect(screen.getByText('Give your project a name.')).toBeInTheDocument();
    expect(screen.getByText('Describe what you want to build.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Describe your project' })).toBeInTheDocument();

    await user.type(screen.getByLabelText(/Design reference URL/), 'nope');
    await completeIdeaStep(user);
    expect(screen.getByText(/Enter a full URL/)).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/Design reference URL/));
    await user.click(screen.getByRole('button', { name: /next/i }));
    expect(screen.getByRole('heading', { name: 'Choose your technology' })).toBeInTheDocument();
  });

  it('rejects incompatible stacks and preserves answers across steps', async () => {
    const { user } = renderApp({ route: '/new' });
    await completeIdeaStep(user);

    await user.click(screen.getByRole('radio', { name: /I'll choose my stack/ }));
    await user.click(screen.getByRole('checkbox', { name: 'React' }));
    await user.click(screen.getByRole('checkbox', { name: 'Next.js' }));
    expect(screen.getByRole('alert')).toHaveTextContent('React and Next.js overlap');

    await user.click(screen.getByRole('button', { name: /next/i }));
    expect(screen.getByRole('heading', { name: 'Choose your technology' })).toBeInTheDocument();

    await user.click(screen.getByRole('checkbox', { name: 'React' }));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();

    // Back to step 1: answers are preserved.
    await user.click(screen.getByRole('button', { name: /back/i }));
    expect(screen.getByLabelText('Project name')).toHaveValue('Atelier');
    await user.click(screen.getByRole('button', { name: /next/i }));
    expect(screen.getByRole('checkbox', { name: 'Next.js' })).toBeChecked();
  });

  it('reviews, edits, confirms, and opens the new workspace', async () => {
    const { user, router, services } = renderApp({ route: '/new' });
    await completeIdeaStep(user);
    await user.click(screen.getByRole('button', { name: /next/i })); // recommend stack
    await user.click(screen.getByRole('checkbox', { name: 'Authentication' }));
    await user.click(screen.getByRole('checkbox', { name: 'Payments' }));
    await user.click(screen.getByRole('button', { name: /next/i }));

    const idea = screen.getByRole('region', { name: 'Project idea' });
    expect(within(idea).getByText('Atelier')).toBeInTheDocument();
    const requirements = screen.getByRole('region', { name: 'Requirements' });
    expect(within(requirements).getByText('Payments')).toBeInTheDocument();

    // Edit jumps back to the relevant step and keeps state.
    await user.click(screen.getByRole('button', { name: 'Edit project idea' }));
    await user.clear(screen.getByLabelText('Project name'));
    await user.type(screen.getByLabelText('Project name'), 'Atelier Commerce');
    for (let i = 0; i < 3; i += 1) await user.click(screen.getByRole('button', { name: /next/i }));

    await user.click(screen.getByRole('button', { name: 'Create project' }));
    const dialog = screen.getByRole('dialog', { name: 'Create this project?' });
    expect(within(dialog).getByText(/not connected yet/)).toBeInTheDocument();

    // Cancel keeps the user on the review step without saving.
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(await services.projects.listProjects()).toHaveLength(0);

    await user.click(screen.getByRole('button', { name: 'Create project' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Create project' }));

    // The workspace renders the summary in both its mobile header and desktop sidebar (CSS hides one).
    expect(await screen.findAllByRole('heading', { level: 1, name: 'Atelier Commerce' })).not.toHaveLength(0);
    expect(router.state.location.pathname).toMatch(/^\/projects\/prj_/);
    const [saved] = await services.projects.listProjects();
    expect(saved?.configuration.requirements.features).toEqual(['authentication', 'payments']);
    expect(saved?.status).toBe('configured');
  });

  it('restores an in-progress draft after remounting', async () => {
    const first = renderApp({ route: '/new' });
    await first.user.type(screen.getByLabelText('Project name'), 'Draft project');
    first.unmount();

    renderApp({ route: '/new' });
    expect(screen.getByLabelText('Project name')).toHaveValue('Draft project');
  });

  // Regression for audit R4: a malformed draft used to crash /new.
  it('discards a malformed persisted draft and starts fresh', async () => {
    window.sessionStorage.setItem(
      'omniora.wizard.draft',
      JSON.stringify({ step: 3, configuration: { name: 'X', stack: { mode: 'custom', technologies: ['cobol'] } } }),
    );
    const { services } = renderApp({ route: '/new' });
    expect(screen.getByRole('heading', { name: 'Describe your project' })).toBeInTheDocument();
    expect(screen.getByLabelText('Project name')).toHaveValue('');
    expect(services.memoryLogger.entries).toContainEqual(expect.objectContaining({ event: 'wizard-draft.discarded' }));
  });

  // Regression for audit R2: a failed save used to navigate to a project that did not exist.
  it('keeps the user on the review step with a safe message when saving fails', async () => {
    const failingStore = {
      get: () => undefined,
      set: () => {
        throw new AppError('storage-unavailable', 'Browser storage is unavailable or full, so changes could not be saved.');
      },
      remove: () => {},
    };
    const { user, router } = renderApp({ route: '/new', services: createTestServices({ projectStore: failingStore }) });
    await completeIdeaStep(user);
    await user.click(screen.getByRole('button', { name: /next/i }));
    await user.click(screen.getByRole('button', { name: /next/i }));
    await user.click(screen.getByRole('button', { name: 'Create project' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Create project' }));

    expect(await screen.findByText(/Browser storage is unavailable or full/)).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/new');
    expect(screen.getByRole('heading', { name: 'Review your project' })).toBeInTheDocument();
  });

  it('keeps working when session storage is unavailable', async () => {
    const blocked = {
      get: () => {
        throw new AppError('storage-unavailable', 'blocked');
      },
      set: () => {
        throw new AppError('storage-unavailable', 'blocked');
      },
      remove: () => {},
    };
    const { user, services } = renderApp({ route: '/new', services: createTestServices({ uiStateStore: blocked }) });
    await completeIdeaStep(user);
    expect(screen.getByRole('heading', { name: 'Choose your technology' })).toBeInTheDocument();
    expect(services.memoryLogger.entries).toContainEqual(expect.objectContaining({ event: 'wizard-draft.save-failed' }));
  });
});
