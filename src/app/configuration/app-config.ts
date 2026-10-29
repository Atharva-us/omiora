import { AppError } from '@/domain/errors';
import { LOG_LEVELS, type LogLevel } from '@/infrastructure/telemetry/logger';
import type { ServiceMode } from '@/services/services-context';

/**
 * Centralised, validated frontend configuration.
 *
 * Everything here comes from `VITE_*` variables, which Vite inlines into the
 * public JavaScript bundle. They are PUBLIC: never put secrets in them. Server
 * credentials (model API keys, database URLs) belong to the backend only.
 */
export type AppConfig =
  | { serviceMode: 'demo'; logLevel: LogLevel; isDevelopment: boolean }
  | { serviceMode: 'api'; apiBaseUrl: string; logLevel: LogLevel; isDevelopment: boolean };

type Environment = Readonly<Record<string, unknown>>;

const SERVICE_MODES: readonly ServiceMode[] = ['demo', 'api'];
// A public variable whose name looks like a credential is almost certainly a mistake.
const SECRET_LOOKING_NAME = /SECRET|PASSWORD|PRIVATE|TOKEN|API_?KEY|CREDENTIAL/i;

function fail(message: string): never {
  throw new AppError('configuration', message);
}

function readString(env: Environment, key: string): string | undefined {
  const value = env[key];
  if (value === undefined || value === '') return undefined;
  if (typeof value !== 'string') fail(`${key} must be a string.`);
  return value.trim();
}

function parseApiBaseUrl(raw: string | undefined, isDevelopment: boolean): string {
  if (!raw) fail('VITE_OMNIORA_API_BASE_URL is required when VITE_OMNIORA_SERVICE_MODE is "api".');
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    fail('VITE_OMNIORA_API_BASE_URL must be an absolute URL, for example https://api.example.com.');
  }
  const isLocal = url.hostname === 'localhost' || url.hostname === '127.0.0.1';
  if (url.protocol !== 'https:' && !(isDevelopment && isLocal && url.protocol === 'http:')) {
    fail('VITE_OMNIORA_API_BASE_URL must use https (plain http is allowed only for localhost in development).');
  }
  if (url.username || url.password) fail('VITE_OMNIORA_API_BASE_URL must not contain credentials.');
  return url.origin + url.pathname.replace(/\/+$/, '');
}

/** Pure parser: pass `import.meta.env` in the app and plain objects in tests. */
export function parseAppConfig(env: Environment): AppConfig {
  const isDevelopment = env.DEV === true;

  const leaked = Object.keys(env).filter((key) => key.startsWith('VITE_') && SECRET_LOOKING_NAME.test(key));
  if (leaked.length > 0) {
    fail(
      `Refusing to start: ${leaked.join(', ')} looks like a secret, and VITE_* variables are embedded in the public bundle. Move it to the backend.`,
    );
  }

  const rawLevel = readString(env, 'VITE_OMNIORA_LOG_LEVEL') ?? (isDevelopment ? 'debug' : 'warn');
  const logLevel = LOG_LEVELS.find((level) => level === rawLevel);
  if (!logLevel) fail(`VITE_OMNIORA_LOG_LEVEL must be one of: ${LOG_LEVELS.join(', ')}.`);

  // Development may default to demo; production builds must choose explicitly so a deployment
  // can never end up on demo adapters by accident.
  const explicitMode = readString(env, 'VITE_OMNIORA_SERVICE_MODE');
  if (!explicitMode && !isDevelopment) {
    fail('VITE_OMNIORA_SERVICE_MODE must be set to "demo" or "api" for production builds.');
  }
  const mode = explicitMode ?? 'demo';
  const serviceMode = SERVICE_MODES.find((candidate) => candidate === mode);
  if (!serviceMode) fail(`VITE_OMNIORA_SERVICE_MODE must be "demo" or "api" (received "${mode}").`);

  if (serviceMode === 'api') {
    return {
      serviceMode,
      apiBaseUrl: parseApiBaseUrl(readString(env, 'VITE_OMNIORA_API_BASE_URL'), isDevelopment),
      logLevel,
      isDevelopment,
    };
  }
  return { serviceMode, logLevel, isDevelopment };
}
