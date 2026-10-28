/* SoAI - Wizard page actions [frontend/assets/ts/pages/wizard/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

type AiSetupActionId = 'wizard-ai-change-provider' | 'wizard-ai-use-cloud' | 'wizard-ai-search-manually' | 'wizard-ai-back-to-provider' | 'wizard-ai-search-result' | 'wizard-ai-search-variant' | 'wizard-ai-row-action' | 'wizard-ai-retry-load';

const AI_SETUP_ACTION_IDS: readonly AiSetupActionId[] = Object.freeze(['wizard-ai-change-provider', 'wizard-ai-use-cloud', 'wizard-ai-search-manually', 'wizard-ai-back-to-provider', 'wizard-ai-search-result', 'wizard-ai-search-variant', 'wizard-ai-row-action', 'wizard-ai-retry-load']);

const { guard: isAiSetupActionId } = createActionIdSet<AiSetupActionId>(...AI_SETUP_ACTION_IDS);

export type WizardActionId = 'wizard-toggle-disclosure' | 'wizard-back' | 'wizard-next' | 'wizard-activate' | 'wizard-activate-evaluation' | 'wizard-reconcile' | 'wizard-export-offline' | 'wizard-import-offline' | 'wizard-start-evaluation' | 'wizard-ai-finish-later' | 'wizard-ai-skip' | AiSetupActionId;

const { guard: isWizardActionId } = createActionIdSet<WizardActionId>('wizard-toggle-disclosure', 'wizard-back', 'wizard-next', 'wizard-activate', 'wizard-activate-evaluation', 'wizard-reconcile', 'wizard-export-offline', 'wizard-import-offline', 'wizard-start-evaluation', 'wizard-ai-finish-later', 'wizard-ai-skip', ...AI_SETUP_ACTION_IDS);

export { isAiSetupActionId, isWizardActionId };
export type { AiSetupActionId };
