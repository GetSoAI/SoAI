/* SoAI - Safe localized licensing error presentation [frontend/assets/ts/core/licensing/errorPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { i18n } from '@core/i18n/index.ts';

const messageForCode = (code: string | undefined): string => {
    switch (code) {
        case 'invalid_credential':
            return i18n.t('licensing.errors.invalidKey');
        case 'personal_capacity_reached':
        case 'production_capacity_reached':
        case 'non_production_capacity_reached':
            return i18n.t('licensing.errors.deploymentLimit');
        case 'licensed_product_scope_mismatch':
            return i18n.t('licensing.errors.productMismatch');
        case 'license_not_effective':
            return i18n.t('licensing.errors.notEffective');
        case 'license_expired':
            return i18n.t('licensing.errors.expired');
        case 'license_suspended':
            return i18n.t('licensing.errors.suspended');
        case 'license_terminated':
            return i18n.t('licensing.errors.terminated');
        case 'license_changed':
            return i18n.t('licensing.errors.licenseChanged');
        case 'evaluation_terms_changed':
            return i18n.t('licensing.errors.termsChanged');
        case 'operation_in_progress':
            return i18n.t('licensing.errors.inProgress');
        case 'activation_not_found':
            return i18n.t('licensing.errors.activationNotFound');
        case 'operation_not_found':
            return i18n.t('licensing.errors.operationNotFound');
        case 'evaluation_ineligible':
            return i18n.t('licensing.errors.evaluationIneligible');
        case 'provider_outcome_unknown':
            return i18n.t('licensing.errors.providerOutcomeUnknown');
        case 'renewal_not_reconciled':
            return i18n.t('licensing.errors.renewalNotReconciled');
        case 'licensing_trust_unavailable':
            return i18n.t('licensing.errors.trustUnavailable');
        case 'wizard_state_changed':
            return i18n.t('licensing.errors.stateChanged');
        default:
            return i18n.t('licensing.errors.actionFailed');
    }
};

const presentLicensingError = <Value>(error: Value): string => {
    if (!(error instanceof APIError)) return i18n.t('licensing.errors.actionFailed');
    const message = messageForCode(error.code);
    return error.traceId ? `${message} ${i18n.t('licensing.errors.reference', { traceId: error.traceId })}` : message;
};

export { presentLicensingError };
