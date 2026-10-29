import { getTechnology } from './catalog';
import type { PlatformTarget, StackPreference, TechnologyId } from './project';

export interface StackValidation {
  errors: string[];
  warnings: string[];
}

const has = (ids: readonly TechnologyId[], id: TechnologyId) => ids.includes(id);

function coversPlatform(ids: readonly TechnologyId[], platform: 'website' | 'mobile'): boolean {
  return ids.some((id) => {
    const technology = getTechnology(id);
    const isClient = technology.category === 'web-frontend' || technology.category === 'mobile';
    return isClient && technology.platforms.includes(platform);
  });
}

/**
 * Checks a custom stack against the chosen platform. Errors block saving;
 * warnings are advisory. "Recommend" mode is always valid because the
 * recommendation itself will be produced later by the planning service.
 */
export function validateStack(platform: PlatformTarget, stack: StackPreference): StackValidation {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (stack.mode === 'recommend') return { errors, warnings };

  const ids = stack.technologies;
  if (ids.length === 0) {
    errors.push('Select at least one technology, or let Omniora recommend a stack.');
    return { errors, warnings };
  }

  if (has(ids, 'react') && has(ids, 'nextjs')) {
    errors.push('React and Next.js overlap (Next.js already includes React). Choose one web framework.');
  }
  if (has(ids, 'flutter') && has(ids, 'react-native')) {
    errors.push('Flutter and React Native are competing mobile frameworks. Choose one.');
  }
  if (has(ids, 'fastapi') && has(ids, 'nodejs')) {
    errors.push('Choose a single backend runtime: Python/FastAPI or Node.js.');
  }

  const needsWeb = platform === 'website' || platform === 'both';
  const needsMobile = platform === 'mobile' || platform === 'both';

  if (needsWeb && !coversPlatform(ids, 'website')) {
    errors.push('A website needs a web client. Add React, Next.js, or Flutter (web).');
  }
  if (needsMobile && !coversPlatform(ids, 'mobile')) {
    errors.push('A mobile app needs a mobile framework. Add Flutter or React Native.');
  }
  if (platform === 'mobile' && (has(ids, 'react') || has(ids, 'nextjs'))) {
    warnings.push('React and Next.js produce websites, so they will not be used in a mobile-only project.');
  }

  const hasServer = has(ids, 'fastapi') || has(ids, 'nodejs') || has(ids, 'nextjs');
  if (has(ids, 'postgresql') && !hasServer) {
    errors.push('PostgreSQL needs a server layer. Add FastAPI, Node.js, or Next.js.');
  }
  if (has(ids, 'flutter') && platform === 'website') {
    warnings.push('Flutter web suits app-like experiences; content and SEO-heavy sites are better served by Next.js.');
  }

  return { errors, warnings };
}
