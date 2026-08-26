/* SoAI - Wizard page contracts constants [frontend/assets/ts/pages/wizard/contracts/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WizardStepId } from '@features/wizard/public.ts';

export const WIZARD_STEP_IDS: ReadonlyArray<WizardStepId> = ['welcome', 'license', 'use', 'account', 'complete'];

export const deriveWizardStepIds = (requiresProductAccess: boolean): ReadonlyArray<WizardStepId> => (requiresProductAccess ? ['welcome', 'license', 'use', 'product_access', 'account', 'complete'] : WIZARD_STEP_IDS);

export const requireWizardStepId = (steps: readonly WizardStepId[], index: number): WizardStepId => {
    const stepId = steps[index];
    if (!stepId) throw new Error(`WizardPage: invalid step index ${String(index)}`);
    return stepId;
};
