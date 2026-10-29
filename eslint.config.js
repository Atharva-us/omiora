import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';
import { defineConfig, globalIgnores } from 'eslint/config';

/**
 * Architectural boundaries (see docs/ARCHITECTURE.md). Each glob block sets
 * the full pattern list for its files, because a later block replaces the
 * rule options of an earlier one rather than merging them.
 */
const restrictImports = (...patterns) => ({
  '@typescript-eslint/no-restricted-imports': ['error', { patterns }],
});

const noUiOrShell = {
  group: ['@/app/**', '@/components/**', '@/features/**', '@/hooks/**'],
  message: 'This layer must not depend on UI code or the app shell.',
};
const noImplementations = {
  group: ['@/services/demo/**', '@/services/unconfigured/**', '@/services/http/**', '@/app/composition/**'],
  message: 'Only the composition root (app/composition) may import concrete service implementations. Use useServices().',
};
const infrastructureTypesOnly = {
  group: ['@/infrastructure/**'],
  allowTypeImports: true,
  message: 'UI code receives infrastructure through useServices(); import its interfaces as types only.',
};

const testFiles = ['**/*.test.{ts,tsx}', 'src/test/**'];

export default defineConfig([
  globalIgnores(['dist', 'coverage']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
  },
  {
    files: ['src/domain/**/*.ts'],
    ignores: testFiles,
    rules: restrictImports(
      {
        group: ['react', 'react-dom', 'react-dom/*', 'react-router-dom', 'lucide-react'],
        message: 'Domain code must stay framework-free.',
      },
      {
        group: ['@/app/**', '@/components/**', '@/features/**', '@/hooks/**', '@/services/**', '@/infrastructure/**', '@/lib/**'],
        message: 'Domain code may depend only on other domain modules and zod.',
      },
    ),
  },
  {
    files: ['src/services/**/*.ts', 'src/infrastructure/**/*.ts', 'src/lib/**/*.ts'],
    ignores: testFiles,
    rules: restrictImports(noUiOrShell),
  },
  {
    files: ['src/components/**/*.{ts,tsx}', 'src/hooks/**/*.ts'],
    ignores: testFiles,
    rules: restrictImports(noImplementations, infrastructureTypesOnly, {
      group: ['@/features/**'],
      message: 'Shared code must not depend on a feature.',
    }),
  },
  {
    files: ['src/features/**/*.{ts,tsx}'],
    ignores: testFiles,
    rules: restrictImports(noImplementations, infrastructureTypesOnly, {
      group: ['@/features/**'],
      message: 'Features must not import other features. Move shared code to domain/, components/, or lib/.',
    }),
  },
  {
    files: testFiles,
    rules: { 'react-refresh/only-export-components': 'off' },
  },
]);
