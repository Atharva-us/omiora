import { describe, expect, it } from 'vitest';
import { validConfiguration } from '@/test/fixtures';
import {
  blockingMessages,
  hasBlockingIssues,
  isHttpUrl,
  normalizeConfiguration,
  PROJECT_LIMITS,
  validateNoteContent,
  validateProjectConfiguration,
  validateProjectName,
} from './rules';

describe('project rules', () => {
  it('limits names after trimming', () => {
    expect(validateProjectName('  ')).toBeDefined();
    expect(validateProjectName(`  ${'a'.repeat(PROJECT_LIMITS.nameMax)}  `)).toBeUndefined();
    expect(validateProjectName('a'.repeat(PROJECT_LIMITS.nameMax + 1))).toBeDefined();
  });

  it('requires non-empty notes within the limit', () => {
    expect(validateNoteContent('')).toBe('Write a note before adding it.');
    expect(validateNoteContent('ok')).toBeUndefined();
    expect(validateNoteContent('x'.repeat(PROJECT_LIMITS.noteMax + 1))).toBeDefined();
  });

  it('accepts only http and https URLs', () => {
    expect(isHttpUrl('https://example.com')).toBe(true);
    expect(isHttpUrl('http://localhost:3000/a')).toBe(true);
    for (const unsafe of ['javascript:alert(1)', 'data:text/html,hi', 'file:///etc/passwd', 'example.com']) {
      expect(isHttpUrl(unsafe)).toBe(false);
    }
  });

  it('combines field and stack problems into one result', () => {
    const issues = validateProjectConfiguration(
      validConfiguration({ name: '', stack: { mode: 'custom', technologies: ['flutter', 'react-native'] }, platform: 'mobile' }),
    );
    expect(issues.fields.name).toBeDefined();
    expect(issues.stackErrors).toHaveLength(1);
    expect(hasBlockingIssues(issues)).toBe(true);
    expect(blockingMessages(issues)).toHaveLength(2);
    expect(hasBlockingIssues(validateProjectConfiguration(validConfiguration()))).toBe(false);
  });

  it('treats warnings as non-blocking', () => {
    const issues = validateProjectConfiguration(
      validConfiguration({ platform: 'website', stack: { mode: 'custom', technologies: ['flutter'] } }),
    );
    expect(issues.stackWarnings).toHaveLength(1);
    expect(hasBlockingIssues(issues)).toBe(false);
  });

  it('normalises whitespace and duplicate selections', () => {
    const normalized = normalizeConfiguration(
      validConfiguration({
        name: ' A ',
        referenceUrl: ' https://example.com ',
        stack: { mode: 'custom', technologies: ['nextjs', 'nextjs'] },
        requirements: { features: ['database', 'database'], custom: ' x ' },
      }),
    );
    expect(normalized).toMatchObject({
      name: 'A',
      referenceUrl: 'https://example.com',
      stack: { mode: 'custom', technologies: ['nextjs'] },
      requirements: { features: ['database'], custom: 'x' },
    });
  });
});
