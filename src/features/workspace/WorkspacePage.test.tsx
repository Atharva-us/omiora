import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { validConfiguration } from '@/test/fixtures';
import { createTestServices, renderApp } from '@/test/render-app';

async function setup() {
  const services = createTestServices();
  const project = await services.projects.createProject(
    validConfiguration({
      description: 'Ticketing platform for support teams',
      name: 'Relay Desk',
      requirements: { features: ['authentication'], custom: 'SLA timers' },
    }),
  );
  const rendered = renderApp({ route: `/projects/${project.id}`, services });
  await screen.findAllByRole('heading', { level: 1, name: 'Relay Desk' });
  return { ...rendered, project };
}

describe('WorkspacePage', () => {
  it('switches tabs with the mouse and keyboard', async () => {
    const { user } = await setup();
    const tabs = screen.getByRole('tablist', { name: 'Workspace views' });
    expect(within(tabs).getByRole('tab', { name: 'Preview' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('No preview available')).toBeInTheDocument();

    await user.click(within(tabs).getByRole('tab', { name: 'Tasks' }));
    expect(screen.getByRole('tabpanel')).toHaveTextContent('SLA timers');
    expect(screen.getByRole('tabpanel')).toHaveTextContent('not an engineering plan');

    await user.keyboard('{ArrowRight}');
    expect(within(tabs).getByRole('tab', { name: 'Tests' })).toHaveFocus();
    expect(screen.getByText('No test runs')).toBeInTheDocument();
  });

  it('opens the real project definition from the explorer', async () => {
    const { user } = await setup();
    await user.click(screen.getAllByRole('button', { name: 'omniora.project.json' })[0]!);
    const panel = screen.getByRole('tabpanel');
    expect(panel).toHaveTextContent('"name": "Relay Desk"');
    expect(within(panel).getByText('Read-only')).toBeInTheDocument();
  });

  it('saves requirement notes without fabricating assistant replies', async () => {
    const { user, services, project } = await setup();
    const composer = screen.getByLabelText('Add a requirement note');
    await user.click(screen.getByRole('button', { name: 'Add note' }));
    expect(screen.getByText('Write a note before adding it.')).toBeInTheDocument();

    await user.type(composer, 'Agents need keyboard shortcuts');
    await user.click(screen.getByRole('button', { name: 'Add note' }));
    const notes = await screen.findByRole('list', { name: 'Requirement notes' });
    expect(within(notes).getAllByRole('listitem')).toHaveLength(1);
    expect(await services.projects.listNotes(project.id)).toHaveLength(1);
    expect(screen.queryByText(/assistant:/i)).not.toBeInTheDocument();
  });

  it('explains that ZIP export is unavailable and offers the JSON definition', async () => {
    const { user } = await setup();
    await user.click(screen.getAllByRole('button', { name: 'Export ZIP' })[0]!);
    const dialog = screen.getByRole('dialog', { name: 'Export project' });
    expect(within(dialog).getByText(/No source code has been generated/)).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renames and deletes a project from settings', async () => {
    const { user, router, services } = await setup();
    await user.click(screen.getAllByRole('button', { name: 'Settings' })[0]!);
    const dialog = screen.getByRole('dialog', { name: 'Project settings' });
    const nameInput = within(dialog).getByLabelText('Project name');
    await user.clear(nameInput);
    await user.type(nameInput, 'Relay Desk 2');
    await user.click(within(dialog).getByRole('button', { name: 'Save name' }));
    expect(await within(dialog).findByText('Saved')).toBeInTheDocument();

    await user.click(within(dialog).getByRole('button', { name: 'Delete project' }));
    await user.click(within(dialog).getByRole('button', { name: 'Yes, delete permanently' }));
    expect(await screen.findByRole('heading', { name: 'Projects' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/projects');
    expect(await services.projects.listProjects()).toEqual([]);
  });

  it('marks sample projects as read-only demo data', async () => {
    renderApp({ route: '/projects/sample_fitness-tracker' });
    expect(await screen.findByText(/This is a sample project \(demo data\)/)).toBeInTheDocument();
    expect(screen.queryByLabelText('Add a requirement note')).not.toBeInTheDocument();
  });

  it('shows a not-found state for unknown projects', async () => {
    renderApp({ route: '/projects/prj_missing' });
    expect(await screen.findByText('Project not found')).toBeInTheDocument();
  });

  it('lists the ten planned agents without claiming any are running', async () => {
    await setup();
    const panel = screen.getByRole('region', { name: 'Agent activity' });
    expect(within(panel).getByText('No agent activity')).toBeInTheDocument();
    expect(within(panel).getAllByText('Planned')).toHaveLength(10);
    expect(within(panel).getByText('Project Manager')).toBeInTheDocument();
    expect(within(panel).getByText('Security & Release')).toBeInTheDocument();
  });
});
