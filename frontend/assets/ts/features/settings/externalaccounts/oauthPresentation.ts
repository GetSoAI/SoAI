/* SoAI - Settings feature OAuth presentation [frontend/assets/ts/features/settings/externalaccounts/oauthPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { OauthStatus } from '@core/api/contracts/oauthContracts.ts';
import { resolveSettingsOauthFailureMessage, resolveSettingsOauthStatusLabel, type SettingsOauthStatusLabelCatalog } from '@features/settings/oauthStatusPresentation.ts';

const getExternalAccountOauthStatusLabels = (): SettingsOauthStatusLabelCatalog => ({
    ready: i18n.t('settings.externalAccounts.shared.oauthStatus.ready'),
    none: i18n.t('settings.externalAccounts.shared.oauthStatus.none'),
    authRequired: i18n.t('settings.externalAccounts.shared.oauthStatus.auth_required'),
    insufficientScope: i18n.t('settings.externalAccounts.shared.oauthStatus.insufficient_scope'),
    expired: i18n.t('settings.externalAccounts.shared.oauthStatus.expired'),
    error: i18n.t('settings.externalAccounts.shared.oauthStatus.error')
});

const resolveExternalAccountOauthStatusLabel = (status: OauthStatus): string => {
    return resolveSettingsOauthStatusLabel(status, getExternalAccountOauthStatusLabels()) ?? i18n.t('settings.externalAccounts.shared.oauthStatus.error');
};

const resolveExternalAccountOauthFailureMessage = (baseMessage: string, status: OauthStatus | null): string => {
    return resolveSettingsOauthFailureMessage(baseMessage, status, getExternalAccountOauthStatusLabels());
};

export { resolveExternalAccountOauthFailureMessage, resolveExternalAccountOauthStatusLabel };
