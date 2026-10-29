import { describe, expect, it } from 'vitest';
import { validateStack } from './stack-validation';

describe('validateStack', () => {
  it('always accepts recommend mode', () => {
    expect(validateStack('both', { mode: 'recommend' })).toEqual({ errors: [], warnings: [] });
  });

  it('requires at least one technology in custom mode', () => {
    expect(validateStack('website', { mode: 'custom', technologies: [] }).errors).toHaveLength(1);
  });

  it('rejects overlapping web frameworks', () => {
    const { errors } = validateStack('website', { mode: 'custom', technologies: ['react', 'nextjs'] });
    expect(errors.some((error) => error.includes('React and Next.js'))).toBe(true);
  });

  it('rejects competing mobile frameworks and backends', () => {
    const { errors } = validateStack('mobile', {
      mode: 'custom',
      technologies: ['flutter', 'react-native', 'fastapi', 'nodejs'],
    });
    expect(errors).toHaveLength(2);
  });

  it('requires a client for the chosen platform', () => {
    expect(validateStack('website', { mode: 'custom', technologies: ['react-native'] }).errors).toContain(
      'A website needs a web client. Add React, Next.js, or Flutter (web).',
    );
    expect(validateStack('mobile', { mode: 'custom', technologies: ['nextjs'] }).errors).toContain(
      'A mobile app needs a mobile framework. Add Flutter or React Native.',
    );
  });

  it('requires a server layer for PostgreSQL', () => {
    expect(validateStack('website', { mode: 'custom', technologies: ['react', 'postgresql'] }).errors).toContain(
      'PostgreSQL needs a server layer. Add FastAPI, Node.js, or Next.js.',
    );
    expect(validateStack('website', { mode: 'custom', technologies: ['nextjs', 'postgresql'] }).errors).toEqual([]);
  });

  it('accepts Flutter alone for web and mobile', () => {
    expect(validateStack('both', { mode: 'custom', technologies: ['flutter'] }).errors).toEqual([]);
  });
});
