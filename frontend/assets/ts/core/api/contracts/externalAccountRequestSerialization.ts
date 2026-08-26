/* SoAI - Frontend external account request serialization [frontend/assets/ts/core/api/contracts/externalAccountRequestSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CalendarAccountWriteRequest, ExternalAccountAuthWrite, MailAccountWriteRequest } from '@core/api/contracts/externalAccountContracts.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const serializeExternalAccountAuth = (auth: ExternalAccountAuthWrite): JsonObject => {
    const serialized: JsonObject = { type: auth.type };
    if (auth.password !== undefined) serialized['password'] = auth.password;
    if (auth.oauth !== undefined) {
        const oauth: JsonObject = {
            'resource_metadata_url': auth.oauth.resourceMetadataUrl,
            'client_id': auth.oauth.clientId,
            'auth_server_issuer': auth.oauth.authServerIssuer,
            'authorization_endpoint': auth.oauth.authorizationEndpoint,
            'token_endpoint': auth.oauth.tokenEndpoint,
            'registration_endpoint': auth.oauth.registrationEndpoint,
            'token_endpoint_auth_method': auth.oauth.tokenEndpointAuthMethod,
            scopes: auth.oauth.scopes,
            'required_scopes': auth.oauth.requiredScopes
        };
        if (auth.oauth.clientSecret !== undefined) oauth['client_secret'] = auth.oauth.clientSecret;
        if (auth.oauth.status !== undefined) oauth['status'] = auth.oauth.status;
        serialized['oauth'] = oauth;
    }
    return serialized;
};

const serializeMailAccountWriteRequest = (request: MailAccountWriteRequest): JsonObject => ({
    label: request.label,
    username: request.username,
    auth: serializeExternalAccountAuth(request.auth),
    transport: {
        protocol: request.transport.protocol,
        'inbound_host': request.transport.inboundHost,
        'inbound_port': request.transport.inboundPort,
        'inbound_security': request.transport.inboundSecurity,
        'smtp_host': request.transport.smtpHost,
        'smtp_port': request.transport.smtpPort,
        'smtp_security': request.transport.smtpSecurity,
        'folder_mapping': request.transport.folderMapping
    }
});

const serializeCalendarAccountWriteRequest = (request: CalendarAccountWriteRequest): JsonObject => ({
    label: request.label,
    username: request.username,
    auth: serializeExternalAccountAuth(request.auth),
    transport: {
        'caldav_base_url': request.transport.caldavBaseUrl,
        'linked_mail_account_id': request.transport.linkedMailAccountId,
        'discovered_principal': request.transport.discoveredPrincipal
    }
});

export { serializeCalendarAccountWriteRequest, serializeMailAccountWriteRequest };
