import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DEMO_STORE_KEY } from '@/services/demo/local-project-service';
import { validConfiguration } from '@/test/fixtures';
import { createTestServices, renderApp } from '@/test/render-app';

describe('ProjectsPage', () => {
  it('shows an honest empty state and clearly labelled samples', async () => {
    renderApp({ route: '/projects' });
    expect(await screen.findByText('No projects yet')).toBeInTheDocument();
    const samples = screen.getByRole('region', { name: 'Sample projects' });
    expect(within(samples).getByText('Demo data')).toBeInTheDocument();
    expect(within(samples).getAllByRole('article').length).toBeGreaterThan(0);
  });

  it('filters by search text and platform, and can hide samples', async () => {
    const services = createTestServices();
    await services.projects.createProject(validConfiguration({ description: 'An online shop for ceramics', name: 'Kiln Store' }));
    await services.projects.createProject(
      validConfiguration({ description: 'Running coach app with plans', name: 'Pace Coach', platform: 'mobile' }),
    );
    const { user } = renderApp({ route: '/projects', services });

    const yours = await screen.findByRole('region', { name: /Your projects/ });
    expect(within(yours).getAllByRole('article')).toHaveLength(2);

    await user.type(screen.getByRole('searchbox', { name: 'Search projects' }), 'ceramics');
    expect(within(yours).getAllByRole('article')).toHaveLength(1);
    expect(within(yours).getByText('Kiln Store')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Clear' }));
    await user.selectOptions(screen.getByRole('combobox', { name: 'Filter by platform' }), 'mobile');
    expect(within(yours).getAllByRole('article')).toHaveLength(1);
    expect(within(yours).getByText('Pace Coach')).toBeInTheDocument();

    await user.type(screen.getByRole('searchbox', { name: 'Search projects' }), 'zzz');
    expect(within(yours).getByText('No projects match your filters')).toBeInTheDocument();

    await user.click(screen.getByRole('checkbox', { name: 'Show sample projects' }));
    const samples = screen.getByRole('region', { name: 'Sample projects' });
    expect(within(samples).queryAllByRole('article')).toHaveLength(0);
  });

  it('ignores invalid URL filter values', async () => {
    renderApp({ route: '/projects?platform=tv&status=bogus&sort=random' });
    expect(await screen.findByRole('combobox', { name: 'Filter by platform' })).toHaveValue('all');
    expect(screen.getByRole('combobox', { name: 'Filter by status' })).toHaveValue('all');
    expect(screen.getByRole('combobox', { name: 'Sort projects' })).toHaveValue('updated');
  });

  // Regression for audit R1: a corrupted record replaced the page with a raw error screen.
  it('still renders valid projects when stored data is partly corrupted', async () => {
    const services = createTestServices();
    await services.projects.createProject(validConfiguration({ name: 'Survivor' }));
    const raw = JSON.parse(window.localStorage.getItem(DEMO_STORE_KEY) ?? '{}') as { projects: object[] };
    raw.projects.push({ id: 'prj_bad', technologies: ['cobol'], configuration: { stack: { mode: 'custom', technologies: ['cobol'] } } });
    window.localStorage.setItem(DEMO_STORE_KEY, JSON.stringify(raw));

    renderApp({ route: '/projects', services });
    const yours = await screen.findByRole('region', { name: /Your projects/ });
    expect(within(yours).getAllByRole('article')).toHaveLength(1);
    expect(within(yours).getByText('Survivor')).toBeInTheDocument();
    expect(screen.queryByText(/Unexpected Application Error/)).not.toBeInTheDocument();
  });

  it('shows a safe, retryable error when storage cannot be read', async () => {
    const services = createTestServices({
      projectStore: {
        get: () => {
          throw new TypeError('internal detail that must not reach the UI');
        },
        set: () => {},
        remove: () => {},
      },
    });
    renderApp({ route: '/projects', services });
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Projects could not be loaded');
    expect(alert).not.toHaveTextContent('internal detail');
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    expect(services.memoryLogger.entries).toContainEqual(expect.objectContaining({ event: 'projects.load-failed' }));
  });
});
