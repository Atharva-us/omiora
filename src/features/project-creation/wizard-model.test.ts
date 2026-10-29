import { describe, expect, it } from 'vitest';
import { validConfiguration } from '@/test/fixtures';
import {
  draftFromConfiguration,
  emptyDraft,
  firstInvalidStep,
  isStepValid,
  parseWizardLocationState,
  parseWizardState,
  toConfiguration,
  validateStep,
  wizardReducer,
  type WizardState,
} from './wizard-model';

const initial = (): WizardState => ({ step: 0, configuration: emptyDraft() });

describe('wizardReducer', () => {
  it('updates idea fields without touching other state', () => {
    const state = wizardReducer(initial(), { type: 'update', patch: { name: 'Atlas' } });
    expect(state.configuration.name).toBe('Atlas');
    expect(state.configuration.stack.mode).toBe('recommend');
  });

  it('toggling a technology switches to custom mode and toggles membership', () => {
    let state = wizardReducer(initial(), { type: 'toggle-technology', id: 'react' });
    expect(state.configuration.stack).toEqual({ mode: 'custom', technologies: ['react'] });
    state = wizardReducer(state, { type: 'toggle-technology', id: 'react' });
    expect(state.configuration.stack.technologies).toEqual([]);
  });

  it('remembers technology picks while recommend mode is selected', () => {
    let state = wizardReducer(initial(), { type: 'toggle-technology', id: 'flutter' });
    state = wizardReducer(state, { type: 'set-stack-mode', mode: 'recommend' });
    expect(state.configuration.stack.technologies).toEqual(['flutter']);
    state = wizardReducer(state, { type: 'set-stack-mode', mode: 'custom' });
    expect(state.configuration.stack).toEqual({ mode: 'custom', technologies: ['flutter'] });
  });

  it('clamps step navigation to the valid range', () => {
    expect(wizardReducer(initial(), { type: 'go-to', step: -3 }).step).toBe(0);
    expect(wizardReducer(initial(), { type: 'go-to', step: 99 }).step).toBe(3);
  });
});

describe('validateStep', () => {
  it('requires a name and a meaningful description', () => {
    const { fieldErrors } = validateStep('idea', emptyDraft());
    expect(fieldErrors.name).toBeDefined();
    expect(fieldErrors.description).toBeDefined();

    const short = validateStep('idea', { ...emptyDraft('too short'), name: 'X' });
    expect(short.fieldErrors.description).toMatch(/at least/);
  });

  it('validates the optional reference URL only when provided', () => {
    const base = { ...emptyDraft('A storefront for handmade goods'), name: 'Shop' };
    expect(isStepValid('idea', base)).toBe(true);
    expect(validateStep('idea', { ...base, referenceUrl: 'not a url' }).fieldErrors.referenceUrl).toBeDefined();
    expect(validateStep('idea', { ...base, referenceUrl: 'javascript:alert(1)' }).fieldErrors.referenceUrl).toBeDefined();
    expect(isStepValid('idea', { ...base, referenceUrl: 'https://example.com' })).toBe(true);
  });

  it('reports the first invalid step', () => {
    const draft = {
      ...emptyDraft('A storefront for handmade goods'),
      name: 'Shop',
      stack: { mode: 'custom' as const, technologies: [] },
    };
    expect(firstInvalidStep(emptyDraft())).toBe(0);
    expect(firstInvalidStep(draft)).toBe(1);
  });
});

describe('draft ↔ domain conversion', () => {
  it('trims input and drops remembered technologies when a recommendation is requested', () => {
    const result = toConfiguration({
      ...emptyDraft('  Description here  '),
      name: '  Name  ',
      stack: { mode: 'recommend', technologies: ['react'] },
    });
    expect(result.name).toBe('Name');
    expect(result.description).toBe('Description here');
    expect(result.stack).toEqual({ mode: 'recommend' });
  });

  it('round-trips a saved configuration', () => {
    const configuration = validConfiguration({ stack: { mode: 'custom', technologies: ['nextjs', 'postgresql'] } });
    expect(toConfiguration(draftFromConfiguration(configuration))).toEqual(configuration);
  });
});

describe('untrusted input parsing', () => {
  it('rejects malformed persisted drafts', () => {
    expect(parseWizardState(initial())).toEqual(initial());
    expect(parseWizardState({ step: 0 })).toBeNull();
    expect(parseWizardState({ step: 0, configuration: { ...emptyDraft(), platform: 'tv' } })).toBeNull();
    // Regression for audit R4: unknown technology ids used to crash the review step.
    expect(
      parseWizardState({ step: 3, configuration: { ...emptyDraft(), stack: { mode: 'custom', technologies: ['cobol'] } } }),
    ).toBeNull();
    expect(parseWizardState({ step: 9, configuration: emptyDraft() })).toBeNull();
  });

  it('accepts only well-formed router state from the landing prompt', () => {
    expect(parseWizardLocationState({ description: 'Build a shop' })).toEqual({ description: 'Build a shop' });
    expect(parseWizardLocationState({ description: 42 })).toBeNull();
    expect(parseWizardLocationState(null)).toBeNull();
    expect(parseWizardLocationState({ description: 'x'.repeat(5000) })).toBeNull();
  });
});
