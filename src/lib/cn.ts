type ClassValue = string | false | null | undefined;

/** Joins conditional class names. Deliberately tiny — no merging semantics. */
export function cn(...classes: ClassValue[]): string {
  return classes.filter(Boolean).join(' ');
}
