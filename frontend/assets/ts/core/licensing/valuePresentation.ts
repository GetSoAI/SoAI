/* SoAI - Localized licensing value presentation [frontend/assets/ts/core/licensing/valuePresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WizardDeclaration, WizardEdition, WizardEntitlementSummary } from '@core/api/contracts/wizardLicensingContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import type { LicensingState } from '@core/licensing/licensingState.ts';

type EntitlementType = WizardEntitlementSummary['entitlementType'];

const presentLicensingState = (state: LicensingState): string => {
    switch (state) {
        case 'personal_declared':
            return i18n.t('settings.licensing.values.states.personalDeclared');
        case 'evaluation_pending':
            return i18n.t('settings.licensing.values.states.evaluationPending');
        case 'evaluation_active':
            return i18n.t('settings.licensing.values.states.evaluationActive');
        case 'evaluation_expiring':
            return i18n.t('settings.licensing.values.states.evaluationExpiring');
        case 'evaluation_expired':
            return i18n.t('settings.licensing.values.states.evaluationExpired');
        case 'commercial_active':
            return i18n.t('settings.licensing.values.states.commercialActive');
        case 'commercial_expiring':
            return i18n.t('settings.licensing.values.states.commercialExpiring');
        case 'commercial_continuity':
            return i18n.t('settings.licensing.values.states.commercialContinuity');
        case 'commercial_expired':
            return i18n.t('settings.licensing.values.states.commercialExpired');
        case 'suspended':
            return i18n.t('settings.licensing.values.states.suspended');
        case 'terminated':
            return i18n.t('settings.licensing.values.states.terminated');
        case 'invalid_signature':
            return i18n.t('settings.licensing.values.states.invalidSignature');
        case 'invalid_binding':
            return i18n.t('settings.licensing.values.states.invalidBinding');
        case 'invalid_contract':
            return i18n.t('settings.licensing.values.states.invalidContract');
        case 'clock_invalid':
            return i18n.t('settings.licensing.values.states.clockInvalid');
        case 'personal_os_perpetual_active':
            return i18n.t('settings.licensing.values.states.personalOsPerpetualActive');
        case 'commercial_perpetual_active':
            return i18n.t('settings.licensing.values.states.commercialPerpetualActive');
    }
};

const presentEntitlementType = (entitlementType: EntitlementType): string => {
    switch (entitlementType) {
        case 'organization_evaluation':
            return i18n.t('settings.licensing.values.grants.organizationEvaluation');
        case 'commercial_term':
            return i18n.t('settings.licensing.values.grants.commercialTerm');
        case 'commercial_continuity':
            return i18n.t('settings.licensing.values.grants.commercialContinuity');
        case 'personal_os_perpetual':
            return i18n.t('settings.licensing.values.grants.personalOsPerpetual');
        case 'commercial_full_perpetual':
            return i18n.t('settings.licensing.values.grants.commercialFullPerpetual');
    }
};

const presentEdition = (edition: WizardEdition): string => (edition === 'soai-core' ? i18n.t('settings.licensing.values.editions.base') : i18n.t('settings.licensing.values.editions.os'));

const presentDeclaration = (declaration: WizardDeclaration | null): string => {
    if (declaration === null) return i18n.t('common.notAvailable');
    return declaration === 'personal' ? i18n.t('settings.licensing.values.declarations.personal') : i18n.t('settings.licensing.values.declarations.organizationCommercial');
};

export { presentDeclaration, presentEdition, presentEntitlementType, presentLicensingState };
