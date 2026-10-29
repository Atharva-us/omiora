/**
 * Client-side id generation for the DEMO adapter only. A real backend
 * assigns ids; UI code never creates them. Uses `getRandomValues` because
 * `randomUUID` is missing in insecure contexts (e.g. a LAN dev server).
 */
export function createDemoId(prefix: string): string {
  const bytes = crypto.getRandomValues(new Uint8Array(6));
  return `${prefix}_${Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')}`;
}
