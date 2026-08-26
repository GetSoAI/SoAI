/* SoAI - OAuth status presentation [frontend/assets/ts/features/settings/oauthStatusPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OauthStatus } from '@core/api/contracts/oauthContracts.ts';

interface SettingsOauthStatusLabelCatalog {
    ready?: string;
    none?: string;
    authRequired: string;
    insufficientScope: string;
    expired: string;
    error: string;
}

const resolveSettingsOauthStatusLabel = (oauthStatus: OauthStatus, labels: SettingsOauthStatusLabelCatalog): string | null => {
    if (oauthStatus === 'ready') {
        return labels.ready ?? null;
    }
    if (oauthStatus === 'none') {
        return labels.none ?? null;
    }
    if (oauthStatus === 'auth_required') {
        return labels.authRequired;
    }
    if (oauthStatus === 'insufficient_scope') {
        return labels.insufficientScope;
    }
    if (oauthStatus === 'expired') {
        return labels.expired;
    }
    if (oauthStatus === 'error') {
        return labels.error;
    }
    return null;
};

const resolveSettingsOauthFailureMessage = (baseMessage: string, oauthStatus: OauthStatus | null, labels: SettingsOauthStatusLabelCatalog): string => {
    if (oauthStatus === null || oauthStatus === 'none' || oauthStatus === 'ready') {
        return baseMessage;
    }
    const statusMessage = resolveSettingsOauthStatusLabel(oauthStatus, labels);
    if (statusMessage === null) {
        return baseMessage;
    }
    return `${baseMessage} ${statusMessage}.`;
};

export { resolveSettingsOauthFailureMessage, resolveSettingsOauthStatusLabel };
export type { SettingsOauthStatusLabelCatalog };
