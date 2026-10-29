import { TECHNOLOGY_IDS, type PlatformTarget, type RequirementId, type TechnologyId } from './project';

export type TechnologyCategory = 'web-frontend' | 'mobile' | 'backend' | 'database';

/**
 * Whether a working Omniora generator exists for this technology.
 * No generators exist yet, so every entry is `planned`.
 */
export type GeneratorSupport = 'planned' | 'experimental' | 'supported';

export interface Technology {
  id: TechnologyId;
  name: string;
  category: TechnologyCategory;
  description: string;
  /** Platforms this technology can produce or serve. */
  platforms: readonly Exclude<PlatformTarget, 'both'>[];
  support: GeneratorSupport;
}

// Keyed by the id union: adding a TechnologyId without a catalog entry is a compile error.
const TECHNOLOGY_CATALOG: Record<TechnologyId, Technology> = {
  react: {
    id: 'react',
    name: 'React',
    category: 'web-frontend',
    description: 'Component-based web interfaces with a Vite toolchain.',
    platforms: ['website'],
    support: 'planned',
  },
  nextjs: {
    id: 'nextjs',
    name: 'Next.js',
    category: 'web-frontend',
    description: 'React framework with routing, SSR, and API routes.',
    platforms: ['website'],
    support: 'planned',
  },
  flutter: {
    id: 'flutter',
    name: 'Flutter',
    category: 'mobile',
    description: 'Single Dart codebase for iOS, Android, and web.',
    platforms: ['mobile', 'website'],
    support: 'planned',
  },
  'react-native': {
    id: 'react-native',
    name: 'React Native',
    category: 'mobile',
    description: 'Native iOS and Android apps written in React.',
    platforms: ['mobile'],
    support: 'planned',
  },
  fastapi: {
    id: 'fastapi',
    name: 'Python / FastAPI',
    category: 'backend',
    description: 'Typed Python APIs with automatic OpenAPI docs.',
    platforms: ['website', 'mobile'],
    support: 'planned',
  },
  nodejs: {
    id: 'nodejs',
    name: 'Node.js',
    category: 'backend',
    description: 'JavaScript/TypeScript services and REST APIs.',
    platforms: ['website', 'mobile'],
    support: 'planned',
  },
  postgresql: {
    id: 'postgresql',
    name: 'PostgreSQL',
    category: 'database',
    description: 'Relational database with strong consistency.',
    platforms: ['website', 'mobile'],
    support: 'planned',
  },
};

export const TECHNOLOGIES: readonly Technology[] = TECHNOLOGY_IDS.map((id) => TECHNOLOGY_CATALOG[id]);

export const CATEGORY_ORDER: readonly TechnologyCategory[] = ['web-frontend', 'mobile', 'backend', 'database'];

export const CATEGORY_LABELS: Record<TechnologyCategory, string> = {
  'web-frontend': 'Web frontend',
  mobile: 'Mobile',
  backend: 'Backend',
  database: 'Database',
};

export const PLATFORM_LABELS: Record<PlatformTarget, string> = {
  website: 'Website',
  mobile: 'Mobile app',
  both: 'Website + mobile',
};

export interface RequirementOption {
  id: RequirementId;
  label: string;
  description: string;
}

export const REQUIREMENTS: readonly RequirementOption[] = [
  { id: 'authentication', label: 'Authentication', description: 'Sign-up, sign-in, and session handling.' },
  { id: 'database', label: 'Database', description: 'Persistent storage with a defined schema.' },
  { id: 'admin-dashboard', label: 'Admin dashboard', description: 'Internal tools to manage content and users.' },
  { id: 'payments', label: 'Payments', description: 'Checkout and subscription billing flows.' },
  { id: 'notifications', label: 'Notifications', description: 'Email, push, or in-app messaging.' },
  { id: 'automated-tests', label: 'Automated tests', description: 'Unit and end-to-end test suites.' },
];

export function getTechnology(id: TechnologyId): Technology {
  return TECHNOLOGY_CATALOG[id];
}

export function technologyNames(ids: readonly TechnologyId[]): string[] {
  return ids.map((id) => getTechnology(id).name);
}

export function requirementLabel(id: RequirementId): string {
  return REQUIREMENTS.find((requirement) => requirement.id === id)?.label ?? id;
}
