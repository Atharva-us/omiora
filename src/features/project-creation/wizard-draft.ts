import type { KeyValueStore } from '@/infrastructure/storage/key-value-store';
import type { Logger } from '@/infrastructure/telemetry/logger';
import { parseWizardState, type WizardState } from './wizard-model';

/**
 * Session persistence for the in-progress new-project draft. Draft saving
 * is best-effort: if storage is unavailable the wizard keeps working and
 * only reload-recovery is lost, so failures are logged, not surfaced.
 */
const DRAFT_KEY = 'omniora.wizard.draft';

export function loadWizardDraft(store: KeyValueStore, logger: Logger): WizardState | null {
  try {
    const raw = store.get(DRAFT_KEY);
    if (raw === undefined) return null;
    const state = parseWizardState(raw);
    if (!state) logger.warn('wizard-draft.discarded', { reason: 'failed validation' });
    return state;
  } catch (error) {
    logger.warn('wizard-draft.load-failed', { error });
    return null;
  }
}

export function saveWizardDraft(store: KeyValueStore, logger: Logger, state: WizardState): void {
  try {
    store.set(DRAFT_KEY, state);
  } catch (error) {
    logger.warn('wizard-draft.save-failed', { error });
  }
}

export function clearWizardDraft(store: KeyValueStore, logger: Logger): void {
  try {
    store.remove(DRAFT_KEY);
  } catch (error) {
    logger.warn('wizard-draft.clear-failed', { error });
  }
}
