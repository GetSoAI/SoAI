/* SoAI - Settings feature OAuth payload [frontend/assets/ts/features/settings/externalaccounts/oauthPayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';
import type { CalendarAccountEntry, CalendarAccountTransportWrite, ExternalAccountAuthType, ExternalAccountEntry, ExternalAccountOauthWrite, MailAccountEntry, MailAccountTransportWrite } from '@core/api/contracts/externalAccountContracts.ts';
import { parseDelimitedList, requireAbsoluteHttpUrl, requireOptionalAbsoluteHttpUrl } from '@features/settings/externalaccounts/valueParsing.ts';

const readOauthPayload = (readTrimmed: (name: string) => string): ExternalAccountOauthWrite => ({
    resourceMetadataUrl: requireAbsoluteHttpUrl(readTrimmed('oauth_resource_metadata_url'), i18n.t('settings.externalAccounts.validation.oauthResourceMetadataUrl')),
    clientId: readTrimmed('oauth_client_id') || null,
    authServerIssuer: requireOptionalAbsoluteHttpUrl(readTrimmed('oauth_auth_server_issuer'), i18n.t('settings.externalAccounts.validation.oauthIssuer')),
    authorizationEndpoint: requireOptionalAbsoluteHttpUrl(readTrimmed('oauth_authorization_endpoint'), i18n.t('settings.externalAccounts.validation.oauthAuthorizationEndpoint')),
    tokenEndpoint: requireOptionalAbsoluteHttpUrl(readTrimmed('oauth_token_endpoint'), i18n.t('settings.externalAccounts.validation.oauthTokenEndpoint')),
    registrationEndpoint: requireOptionalAbsoluteHttpUrl(readTrimmed('oauth_registration_endpoint'), i18n.t('settings.externalAccounts.validation.oauthRegistrationEndpoint')),
    tokenEndpointAuthMethod: readTrimmed('oauth_token_endpoint_auth_method') || null,
    scopes: parseDelimitedList(readTrimmed('oauth_scopes')),
    requiredScopes: parseDelimitedList(readTrimmed('oauth_required_scopes'))
});

const maybeResetOauthState = (payload: ExternalAccountOauthWrite, authType: ExternalAccountAuthType, changed: boolean): void => {
    if (authType !== 'oauth2' || !changed) {
        return;
    }
    payload['status'] = 'none';
};

const didOauthSettingsChange = (account: ExternalAccountEntry | null, payload: ExternalAccountOauthWrite & { username: string }, transportChanged: boolean, clientSecret: string): boolean => {
    if (account === null || account.auth.type !== 'oauth2') {
        return true;
    }
    return account.username !== payload.username || transportChanged || account.auth.oauth.resourceMetadataUrl !== payload.resourceMetadataUrl || account.auth.oauth.clientId !== payload.clientId || account.auth.oauth.authServerIssuer !== payload.authServerIssuer || account.auth.oauth.authorizationEndpoint !== payload.authorizationEndpoint || account.auth.oauth.tokenEndpoint !== payload.tokenEndpoint || account.auth.oauth.registrationEndpoint !== payload.registrationEndpoint || account.auth.oauth.tokenEndpointAuthMethod !== payload.tokenEndpointAuthMethod || stableJsonStringify(account.auth.oauth.scopes) !== stableJsonStringify(payload.scopes) || stableJsonStringify(account.auth.oauth.requiredScopes) !== stableJsonStringify(payload.requiredScopes) || clientSecret.length > 0;
};

const didMailTransportChange = (account: MailAccountEntry | null, payload: MailAccountTransportWrite): boolean => {
    if (account === null) {
        return true;
    }
    return account.transport.protocol !== payload.protocol || account.transport.inbound.host !== payload.inboundHost || account.transport.inbound.port !== payload.inboundPort || account.transport.inbound.security !== payload.inboundSecurity || account.transport.outbound.host !== payload.smtpHost || account.transport.outbound.port !== payload.smtpPort || account.transport.outbound.security !== payload.smtpSecurity || stableJsonStringify(account.transport.folderMapping) !== stableJsonStringify(payload.folderMapping);
};

const didCalendarTransportChange = (account: CalendarAccountEntry | null, payload: CalendarAccountTransportWrite): boolean => {
    if (account === null) {
        return true;
    }
    return account.transport.caldavBaseUrl !== payload.caldavBaseUrl || account.transport.linkedMailAccountId !== payload.linkedMailAccountId || stableJsonStringify(account.transport.discoveredPrincipal) !== stableJsonStringify(payload.discoveredPrincipal);
};

export { didCalendarTransportChange, didMailTransportChange, didOauthSettingsChange, maybeResetOauthState, readOauthPayload };
