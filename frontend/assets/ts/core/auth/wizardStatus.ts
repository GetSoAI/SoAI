/* SoAI - Shared auth wizard status [frontend/assets/ts/core/auth/wizardStatus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WizardStatus } from '@core/auth/types.ts';

const isFreshInstallWizardStatus = (status: WizardStatus | null): status is WizardStatus => {
    return status !== null && status.setupNeeded === true && status.hasUsers === false;
};

const isWizardSetupCompleteStatus = (status: WizardStatus | null): status is WizardStatus => {
    return status !== null && status.setupNeeded === false && status.hasUsers === true;
};

const isWizardSetupNeededSnapshot = <T>(value: T): boolean => {
    return typeof value === 'object' && value !== null && 'setupNeeded' in value && value.setupNeeded === true;
};

export { isFreshInstallWizardStatus, isWizardSetupCompleteStatus, isWizardSetupNeededSnapshot };
