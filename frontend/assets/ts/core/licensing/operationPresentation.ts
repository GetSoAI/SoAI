/* SoAI - Localized durable licensing operation presentation [frontend/assets/ts/core/licensing/operationPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WizardOperationState } from '@core/api/contracts/wizardLicensingContracts.ts';
import { i18n } from '@core/i18n/index.ts';

const presentLicensingOperationState = (state: WizardOperationState): string => {
    switch (state) {
        case 'prepared':
            return i18n.t('licensing.operations.prepared');
        case 'sending':
            return i18n.t('licensing.operations.sending');
        case 'outcome_unknown':
            return i18n.t('licensing.operations.outcomeUnknown');
        case 'reconciling':
            return i18n.t('licensing.operations.reconciling');
        case 'retry_wait':
            return i18n.t('licensing.operations.retryWait');
        case 'succeeded':
            return i18n.t('licensing.operations.succeeded');
        case 'failed':
            return i18n.t('licensing.operations.failed');
        case 'cancelled':
            return i18n.t('licensing.operations.cancelled');
    }
};

export { presentLicensingOperationState };
