import {
  Boxes,
  FileArchive,
  FlaskConical,
  MonitorSmartphone,
  ScanEye,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';

export const EXAMPLE_PROMPTS = [
  'Build a premium fashion e-commerce website',
  'Create a Flutter fitness tracking application',
  'Build an AI-powered customer support platform',
  'Create a SaaS analytics dashboard',
] as const;

export type FeatureAvailability = 'preview' | 'in-development';

export interface Feature {
  title: string;
  description: string;
  icon: LucideIcon;
  availability: FeatureAvailability;
}

/** Copy describes goals, not shipped capabilities. Availability mirrors services/engine/capabilities.ts. */
export const FEATURES: readonly Feature[] = [
  {
    title: 'Idea to Application',
    description:
      'Start from a plain-language description. Omniora structures it into a project configuration (platform, stack, and requirements) that the engine will build from.',
    icon: Sparkles,
    availability: 'preview',
  },
  {
    title: 'Reference-to-Design Intelligence',
    description:
      'Point to a site you admire. The analysis service is designed to extract its design language (layout, typography, and palette) without copying assets.',
    icon: ScanEye,
    availability: 'in-development',
  },
  {
    title: 'Multi-Agent Engineering',
    description:
      'Specialised agents for planning, interface, backend, and review, coordinated by an orchestrator that keeps every change traceable.',
    icon: Boxes,
    availability: 'in-development',
  },
  {
    title: 'Automated Testing and Repair',
    description:
      'Generated code is built and tested inside isolated sandboxes. Failures feed a repair loop instead of reaching you.',
    icon: FlaskConical,
    availability: 'in-development',
  },
  {
    title: 'Cross-Platform Development',
    description:
      'One project definition for websites, mobile apps, or both, targeting React, Next.js, Flutter, React Native, FastAPI, and Node.js.',
    icon: MonitorSmartphone,
    availability: 'in-development',
  },
  {
    title: 'Downloadable Source Code',
    description:
      'Export a complete, readable repository as a ZIP. No proprietary runtime and no lock-in: the code is yours.',
    icon: FileArchive,
    availability: 'in-development',
  },
];

export const STEPS = [
  {
    title: 'Describe your idea.',
    description: 'Explain what you want in your own words, from a single sentence to a detailed brief.',
  },
  {
    title: 'Define requirements and design references.',
    description: 'Choose platforms, a stack (or ask for a recommendation), core features, and visual references.',
  },
  {
    title: 'Generate and refine the application.',
    description: 'Agents plan and write the code while you review progress and steer with follow-up instructions.',
  },
  {
    title: 'Test, review, and export the project.',
    description: 'Builds and tests run in isolation. Inspect the results, then download the full source.',
  },
] as const;
