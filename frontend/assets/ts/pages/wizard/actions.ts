/* SoAI - Wizard page actions [frontend/assets/ts/pages/wizard/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

export type WizardActionId = 'wizard-back' | 'wizard-next' | 'wizard-activate' | 'wizard-activate-evaluation' | 'wizard-reconcile' | 'wizard-export-offline' | 'wizard-import-offline' | 'wizard-start-evaluation';

const { guard: isWizardActionId } = createActionIdSet<WizardActionId>('wizard-back', 'wizard-next', 'wizard-activate', 'wizard-activate-evaluation', 'wizard-reconcile', 'wizard-export-offline', 'wizard-import-offline', 'wizard-start-evaluation');

export { isWizardActionId };
