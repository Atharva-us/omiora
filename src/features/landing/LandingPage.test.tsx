import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '@/test/render-app';

describe('LandingPage', () => {
  it('renders the brand, hero, and required sections', () => {
    renderApp();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('The Intelligence to Build Anything.');
    const homeLink = screen.getAllByRole('link', { name: 'Omniora home' })[0]!;
    const logo = homeLink.querySelector('img');
    expect(logo?.getAttribute('src')).toMatch(/logo.*\.png/);
    // Rendered at the asset's native 110×115 aspect ratio.
    expect(Number(logo?.getAttribute('width')) / Number(logo?.getAttribute('height'))).toBeCloseTo(110 / 115, 1);
    for (const id of ['product', 'features', 'how-it-works', 'developers']) {
      expect(document.getElementById(id)).not.toBeNull();
    }
    expect(screen.getByText('Illustrative mockup, not live output')).toBeInTheDocument();
  });

  it('labels every capability with its real availability', () => {
    renderApp();
    const features = document.getElementById('features')!;
    expect(within(features).getAllByRole('listitem')).toHaveLength(6);
    expect(within(features).getAllByText('In development')).toHaveLength(5);
  });

  it('shows a dynamic copyright year', () => {
    renderApp();
    expect(screen.getByText(`© ${new Date().getFullYear()} Omniora. All rights reserved.`)).toBeInTheDocument();
  });

  it('opens and closes the mobile menu', async () => {
    const { user } = renderApp();
    const toggle = screen.getByRole('button', { name: 'Open menu' });
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(document.getElementById('mobile-menu')).not.toBeNull();
    await user.keyboard('{Escape}');
    expect(document.getElementById('mobile-menu')).toBeNull();
  });
});
