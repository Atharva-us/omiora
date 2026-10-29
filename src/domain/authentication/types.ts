export interface Credentials {
  email: string;
  password: string;
}

export interface RegistrationInput extends Credentials {
  name: string;
}

/** The only user representation the UI ever sees. Tokens never reach JavaScript. */
export interface AuthUser {
  id: string;
  email: string;
  name: string;
}

export const PASSWORD_MIN_LENGTH = 8;

export function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}
