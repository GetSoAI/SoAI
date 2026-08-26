/* SoAI - Frontend external account boundary contracts [frontend/assets/ts/core/api/contracts/externalAccountContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { decodeOauthStatus, type OauthStatus } from '@core/api/contracts/oauthContracts.ts';
import { readRequiredTrimmedStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { readNullableFiniteIntegerValue, readRequiredFiniteIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readNullableJsonObjectValue, readNullableTrimmedStringRecordValue, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readAllowedStringValue, readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredEnumValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

type ExternalAccountType = 'mail' | 'calendar';
type ExternalAccountAuthType = 'password' | 'oauth2';
type MailAccountSupportedAction = 'delete' | 'test' | 'sync' | 'compose' | 'oauth_connect' | 'oauth_clear';
type CalendarAccountSupportedAction = 'delete' | 'test' | 'sync' | 'oauth_connect' | 'oauth_clear';
type MailProtocol = 'imap' | 'pop3';
type MailSecurity = 'tls' | 'starttls';

interface ExternalAccountOAuthState {
    status: OauthStatus;
    expiresAtMs: number | null;
    hasRefreshToken: boolean;
    clientId: string | null;
    resourceMetadataUrl: string | null;
    authServerIssuer: string | null;
    authorizationEndpoint: string | null;
    tokenEndpoint: string | null;
    registrationEndpoint: string | null;
    tokenEndpointAuthMethod: string | null;
    scopes: string[];
    requiredScopes: string[];
}
interface ExternalAccountAuthState {
    type: ExternalAccountAuthType;
    hasPassword: boolean;
    oauth: ExternalAccountOAuthState;
}
interface ExternalAccountSyncState {
    lastSyncAtMs: number | null;
    lastSyncError: string | null;
}
interface MailAccountCapabilities {
    supportsSync: boolean;
    supportsOauth: boolean;
    supportsDrafts: boolean;
    supportsFolderMutation: boolean;
}
interface CalendarAccountCapabilities {
    supportsSync: boolean;
    supportsOauth: boolean;
    supportsLinkedMailAccount: boolean;
}
interface MailAccountTransport {
    protocol: MailProtocol;
    inbound: { host: string | null; port: number | null; security: MailSecurity | null };
    outbound: { host: string | null; port: number | null; security: MailSecurity | null };
    folderMapping: Record<string, string> | null;
}
interface CalendarAccountTransport {
    caldavBaseUrl: string | null;
    discoveredPrincipal: JsonObject | null;
    linkedMailAccountId: string | null;
}
interface ExternalAccountEntryBase<AccountType extends ExternalAccountType, Transport, Capabilities, Action extends string> {
    accountId: string;
    accountType: AccountType;
    label: string;
    username: string | null;
    auth: ExternalAccountAuthState;
    sync: ExternalAccountSyncState;
    supportedActions: Action[];
    capabilities: Capabilities;
    transport: Transport;
}
type MailAccountEntry = ExternalAccountEntryBase<'mail', MailAccountTransport, MailAccountCapabilities, MailAccountSupportedAction>;
type CalendarAccountEntry = ExternalAccountEntryBase<'calendar', CalendarAccountTransport, CalendarAccountCapabilities, CalendarAccountSupportedAction>;
type ExternalAccountEntry = MailAccountEntry | CalendarAccountEntry;
interface ExternalAccountActionResponse {
    ok: boolean;
    accountId: string;
    accountType: ExternalAccountType;
    status: string | null;
    details: JsonObject | null;
    redirectUrl: string | null;
}
interface ExternalAccountOauthWrite {
    resourceMetadataUrl: string;
    clientId: string | null;
    authServerIssuer: string | null;
    authorizationEndpoint: string | null;
    tokenEndpoint: string | null;
    registrationEndpoint: string | null;
    tokenEndpointAuthMethod: string | null;
    scopes: string[];
    requiredScopes: string[];
    clientSecret?: string | null;
    status?: 'none';
}
interface ExternalAccountAuthWrite {
    type: ExternalAccountAuthType;
    password?: string;
    oauth?: ExternalAccountOauthWrite;
}
interface ExternalAccountWriteRequest<Transport> {
    label: string;
    username: string;
    auth: ExternalAccountAuthWrite;
    transport: Transport;
}
interface MailAccountTransportWrite {
    protocol: MailProtocol;
    inboundHost: string;
    inboundPort: number;
    inboundSecurity: MailSecurity;
    smtpHost: string;
    smtpPort: number;
    smtpSecurity: MailSecurity;
    folderMapping: Record<string, string> | null;
}
interface CalendarAccountTransportWrite {
    caldavBaseUrl: string;
    linkedMailAccountId: string | null;
    discoveredPrincipal: JsonObject | null;
}
type MailAccountWriteRequest = ExternalAccountWriteRequest<MailAccountTransportWrite>;
type CalendarAccountWriteRequest = ExternalAccountWriteRequest<CalendarAccountTransportWrite>;

const AUTH_TYPES: readonly ExternalAccountAuthType[] = ['password', 'oauth2'];
const MAIL_PROTOCOLS: readonly MailProtocol[] = ['imap', 'pop3'];
const MAIL_SECURITIES: readonly MailSecurity[] = ['tls', 'starttls'];
const MAIL_ACTIONS: readonly MailAccountSupportedAction[] = ['delete', 'test', 'sync', 'compose', 'oauth_connect', 'oauth_clear'];
const CALENDAR_ACTIONS: readonly CalendarAccountSupportedAction[] = ['delete', 'test', 'sync', 'oauth_connect', 'oauth_clear'];

const decodeActions = <Action extends string>(value: JsonValue | undefined, label: string, allowed: readonly Action[]): Action[] => {
    const values = readRequiredTrimmedStringArrayValue(value, label);
    const actions: Action[] = [];
    for (const entry of values) {
        const action = readAllowedStringValue(entry, allowed);
        if (action === null) throw new TypeError(`${label} entry is invalid: ${entry}`);
        if (actions.includes(action)) throw new TypeError(`${label} entry is duplicated: ${entry}`);
        actions.push(action);
    }
    return actions;
};

const decodeAuth = (value: JsonValue | undefined): ExternalAccountAuthState => {
    const auth = requireRecord(value, 'External account auth');
    const oauth = requireRecord(auth['oauth'], 'External account auth.oauth');
    return {
        type: readRequiredEnumValue(auth['type'], 'External account auth.type', AUTH_TYPES),
        hasPassword: readRequiredBooleanValue(auth['has_password'], 'External account auth.has_password'),
        oauth: {
            status: decodeOauthStatus(oauth['status'], 'External account auth.oauth.status'),
            expiresAtMs: readNullableFiniteIntegerValue(oauth['expires_at_ms'], 'External account auth.oauth.expires_at_ms'),
            hasRefreshToken: readRequiredBooleanValue(oauth['has_refresh_token'], 'External account auth.oauth.has_refresh_token'),
            clientId: readNullableTrimmedStringValue(oauth['client_id'], 'External account auth.oauth.client_id'),
            resourceMetadataUrl: readNullableTrimmedStringValue(oauth['resource_metadata_url'], 'External account auth.oauth.resource_metadata_url'),
            authServerIssuer: readNullableTrimmedStringValue(oauth['auth_server_issuer'], 'External account auth.oauth.auth_server_issuer'),
            authorizationEndpoint: readNullableTrimmedStringValue(oauth['authorization_endpoint'], 'External account auth.oauth.authorization_endpoint'),
            tokenEndpoint: readNullableTrimmedStringValue(oauth['token_endpoint'], 'External account auth.oauth.token_endpoint'),
            registrationEndpoint: readNullableTrimmedStringValue(oauth['registration_endpoint'], 'External account auth.oauth.registration_endpoint'),
            tokenEndpointAuthMethod: readNullableTrimmedStringValue(oauth['token_endpoint_auth_method'], 'External account auth.oauth.token_endpoint_auth_method'),
            scopes: readRequiredTrimmedStringArrayValue(oauth['scopes'], 'External account auth.oauth.scopes'),
            requiredScopes: readRequiredTrimmedStringArrayValue(oauth['required_scopes'], 'External account auth.oauth.required_scopes')
        }
    };
};

const decodeBase = <AccountType extends ExternalAccountType, Action extends string, Capabilities>(record: JsonObject, type: AccountType, actions: Action[], capabilities: Capabilities) => {
    if (record['account_type'] !== type) throw new TypeError(`External account type is invalid: ${type}`);
    const sync = requireRecord(record['sync'], 'External account sync');
    return { accountId: readRequiredTrimmedStringValue(record['account_id'], `${type} account_id`), accountType: type, label: readRequiredTrimmedStringValue(record['label'], `${type} label`), username: readNullableTrimmedStringValue(record['username'], `${type} username`), auth: decodeAuth(record['auth']), sync: { lastSyncAtMs: readNullableFiniteIntegerValue(sync['last_sync_at_ms'], 'External account sync.last_sync_at_ms'), lastSyncError: readNullableTrimmedStringValue(sync['last_sync_error'], 'External account sync.last_sync_error') }, supportedActions: actions, capabilities };
};

const decodeMailAccount = (value: ApiResponsePayload): MailAccountEntry => {
    const record = requireRecord(value, 'Mail account entry');
    const capabilities = requireRecord(record['capabilities'], 'Mail account capabilities');
    const transport = requireRecord(record['transport'], 'Mail account transport');
    const inbound = requireRecord(transport['inbound'], 'Mail account transport.inbound');
    const outbound = requireRecord(transport['outbound'], 'Mail account transport.outbound');
    const security = (candidate: JsonValue | undefined, label: string): MailSecurity | null => (candidate === null || candidate === undefined ? null : readRequiredEnumValue(candidate, label, MAIL_SECURITIES));
    return {
        ...decodeBase(record, 'mail', decodeActions(record['supported_actions'], 'Mail supported_actions', MAIL_ACTIONS), { supportsSync: readRequiredBooleanValue(capabilities['supports_sync'], 'Mail account capabilities.supports_sync'), supportsOauth: readRequiredBooleanValue(capabilities['supports_oauth'], 'Mail account capabilities.supports_oauth'), supportsDrafts: readRequiredBooleanValue(capabilities['supports_drafts'], 'Mail account capabilities.supports_drafts'), supportsFolderMutation: readRequiredBooleanValue(capabilities['supports_folder_mutation'], 'Mail account capabilities.supports_folder_mutation') }),
        transport: { protocol: readRequiredEnumValue(transport['protocol'], 'Mail account transport.protocol', MAIL_PROTOCOLS), inbound: { host: readNullableTrimmedStringValue(inbound['host'], 'Mail inbound.host'), port: readNullableFiniteIntegerValue(inbound['port'], 'Mail inbound.port'), security: security(inbound['security'], 'Mail inbound.security') }, outbound: { host: readNullableTrimmedStringValue(outbound['host'], 'Mail outbound.host'), port: readNullableFiniteIntegerValue(outbound['port'], 'Mail outbound.port'), security: security(outbound['security'], 'Mail outbound.security') }, folderMapping: readNullableTrimmedStringRecordValue(transport['folder_mapping'], 'Mail folder_mapping') }
    };
};

const decodeCalendarAccount = (value: ApiResponsePayload): CalendarAccountEntry => {
    const record = requireRecord(value, 'Calendar account entry');
    const capabilities = requireRecord(record['capabilities'], 'Calendar account capabilities');
    const transport = requireRecord(record['transport'], 'Calendar account transport');
    return { ...decodeBase(record, 'calendar', decodeActions(record['supported_actions'], 'Calendar supported_actions', CALENDAR_ACTIONS), { supportsSync: readRequiredBooleanValue(capabilities['supports_sync'], 'Calendar account capabilities.supports_sync'), supportsOauth: readRequiredBooleanValue(capabilities['supports_oauth'], 'Calendar account capabilities.supports_oauth'), supportsLinkedMailAccount: readRequiredBooleanValue(capabilities['supports_linked_mail_account'], 'Calendar account capabilities.supports_linked_mail_account') }), transport: { caldavBaseUrl: readNullableTrimmedStringValue(transport['caldav_base_url'], 'Calendar caldav_base_url'), discoveredPrincipal: readNullableJsonObjectValue(transport['discovered_principal'], 'Calendar discovered_principal'), linkedMailAccountId: readNullableTrimmedStringValue(transport['linked_mail_account_id'], 'Calendar linked_mail_account_id') } };
};

const decodeAccountList = <Account>(value: ApiResponsePayload, type: ExternalAccountType, decoder: (entry: ApiResponsePayload) => Account): Account[] => {
    const record = requireRecord(value, `${type} accounts response`);
    const items = record['items'];
    if (!Array.isArray(items)) throw new TypeError(`${type} accounts response.items must be an array`);
    const count = readRequiredFiniteIntegerValue(record['count'], `${type} accounts response.count`);
    if (count !== items.length) throw new TypeError(`${type} accounts response count is invalid`);
    return items.map(decoder);
};

const decodeExternalAccountAction = (value: ApiResponsePayload, expectedType: ExternalAccountType): ExternalAccountActionResponse => {
    const record = requireRecord(value, 'External account action response');
    const accountType = readRequiredEnumValue(record['account_type'], 'External account action response.account_type', ['mail', 'calendar']);
    if (accountType !== expectedType) throw new TypeError(`External account action response.account_type must be ${expectedType}`);
    return { ok: readRequiredBooleanValue(record['ok'], 'External account action response.ok'), accountId: readRequiredTrimmedStringValue(record['account_id'], 'External account action response.account_id'), accountType: accountType, status: readNullableTrimmedStringValue(record['status'], 'External account action response.status'), details: readNullableJsonObjectValue(record['details'], 'External account action response.details'), redirectUrl: readNullableTrimmedStringValue(record['redirect_url'], 'External account action response.redirect_url') };
};

const decodeExternalAccountOauthStatus = (value: ApiResponsePayload, expectedType: ExternalAccountType): OauthStatus => {
    const response = decodeExternalAccountAction(value, expectedType);
    return decodeOauthStatus(response.status, 'External account OAuth status response.status');
};

export { decodeAccountList, decodeCalendarAccount, decodeExternalAccountAction, decodeExternalAccountOauthStatus, decodeMailAccount };
export type { CalendarAccountCapabilities, CalendarAccountEntry, CalendarAccountSupportedAction, CalendarAccountTransportWrite, CalendarAccountWriteRequest, ExternalAccountActionResponse, ExternalAccountAuthState, ExternalAccountAuthType, ExternalAccountAuthWrite, ExternalAccountEntry, ExternalAccountOauthWrite, ExternalAccountType, ExternalAccountWriteRequest, MailAccountCapabilities, MailAccountEntry, MailAccountSupportedAction, MailAccountTransportWrite, MailAccountWriteRequest, MailProtocol, MailSecurity };
