/* SoAI - Messaging account API boundary contracts [frontend/assets/ts/core/api/contracts/messagingAccountContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { parseConversationModelSettings } from '@core/chat/executionSettingsMapping.ts';
import type { ConversationModelSettings } from '@core/chat/executionSettingsTypes.ts';
import { readRequiredFiniteIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredEnumValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { parseMcpToolList } from '@core/mcp/configParsing.ts';
import type { McpFormCatalog } from '@core/mcp/configTypes.ts';
import { readRequiredTrimmedStringArrayValue } from '@core/types/payloadArrayReaders.ts';

type MessagingPlatform = 'telegram' | 'whatsapp' | 'discord';
type MessagingAccountLifecycleState = 'enabled' | 'disabled' | 'deleting' | 'degraded';
type MessagingAccountLocale = 'en' | 'it';
type MessagingCallbackOwnershipState = 'unknown' | 'owned' | 'external' | 'lost' | 'not_applicable';

interface MessagingAuthorizedSender {
    senderId: string;
    displayLabel: string | null;
}

interface MessagingAccount {
    accountId: string;
    platform: MessagingPlatform;
    label: string;
    principalId: string;
    principalLabel: string | null;
    parentPrincipalId: string | null;
    applicationPrincipalId: string | null;
    credentialConfigured: boolean;
    modelSettings: ConversationModelSettings;
    locale: MessagingAccountLocale;
    lifecycleState: MessagingAccountLifecycleState;
    revision: number;
    lifecycleGeneration: number;
    plaintextSecretRepliesEnabled: boolean;
    acceptMessagesFromAnyone: boolean;
    installedCallbackFingerprint: string | null;
    callbackOwnershipState: MessagingCallbackOwnershipState;
    healthCode: string | null;
    healthCheckedAtMs: number | null;
    createdAtMs: number;
    updatedAtMs: number;
    authorizedSenders: MessagingAuthorizedSender[];
}

interface TelegramMessagingCredentials {
    platform: 'telegram';
    botToken: string;
    webhookSecret: string;
}

interface WhatsAppMessagingCredentials {
    platform: 'whatsapp';
    accessToken: string;
    phoneNumberId: string;
    businessAccountId: string;
    applicationId: string;
    apiVersion: string;
    appSecret: string;
    verifyToken: string;
}

interface DiscordMessagingCredentials {
    platform: 'discord';
    botToken: string;
    applicationId: string;
}

type MessagingCredentials = TelegramMessagingCredentials | WhatsAppMessagingCredentials | DiscordMessagingCredentials;

interface MessagingAccountWrite {
    label: string;
    credentials: MessagingCredentials | null;
    modelSettings: ConversationModelSettings;
    locale: MessagingAccountLocale;
    plaintextSecretRepliesEnabled: boolean;
    acceptMessagesFromAnyone: boolean;
    replaceExistingCallback: boolean;
    authorizedSenders: MessagingAuthorizedSender[];
}

interface MessagingAccountCreate extends MessagingAccountWrite {
    credentials: MessagingCredentials;
}

interface MessagingAccountUpdate extends MessagingAccountWrite {
    expectedRevision: number;
    enabled: boolean;
}

const MESSAGING_PLATFORMS: readonly MessagingPlatform[] = ['telegram', 'whatsapp', 'discord'];
const MESSAGING_ACCOUNT_STATES: readonly MessagingAccountLifecycleState[] = ['enabled', 'disabled', 'deleting', 'degraded'];
const MESSAGING_ACCOUNT_LOCALES: readonly MessagingAccountLocale[] = ['en', 'it'];
const MESSAGING_CALLBACK_OWNERSHIP_STATES: readonly MessagingCallbackOwnershipState[] = ['unknown', 'owned', 'external', 'lost', 'not_applicable'];

const decodeAuthorizedSenders = (value: ApiResponsePayload, label: string): MessagingAuthorizedSender[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    const senders: MessagingAuthorizedSender[] = [];
    const senderIds = new Set<string>();
    for (const entry of value) {
        const record = requireRecord(entry, `${label} entry`);
        const senderId = readRequiredTrimmedStringValue(record['sender_id'], `${label} sender_id`);
        if (senderIds.has(senderId)) throw new TypeError(`${label} contains a duplicate sender_id`);
        senderIds.add(senderId);
        senders.push({
            senderId,
            displayLabel: readNullableTrimmedStringValue(record['display_label'], `${label} display_label`)
        });
    }
    return senders;
};

const decodeMessagingAccount = (value: ApiResponsePayload): MessagingAccount => {
    const record = requireRecord(value, 'Messaging account');
    const healthCheckedAt = record['health_checked_at_ms'];
    return {
        accountId: readRequiredTrimmedStringValue(record['account_id'], 'Messaging account account_id'),
        platform: readRequiredEnumValue(record['platform'], 'Messaging account platform', MESSAGING_PLATFORMS),
        label: readRequiredTrimmedStringValue(record['label'], 'Messaging account label'),
        principalId: readRequiredTrimmedStringValue(record['principal_id'], 'Messaging account principal_id'),
        principalLabel: readNullableTrimmedStringValue(record['principal_label'], 'Messaging account principal_label'),
        parentPrincipalId: readNullableTrimmedStringValue(record['parent_principal_id'], 'Messaging account parent_principal_id'),
        applicationPrincipalId: readNullableTrimmedStringValue(record['application_principal_id'], 'Messaging account application_principal_id'),
        credentialConfigured: readRequiredBooleanValue(record['credential_configured'], 'Messaging account credential_configured'),
        modelSettings: parseConversationModelSettings(record['model_settings']),
        locale: readRequiredEnumValue(record['locale'], 'Messaging account locale', MESSAGING_ACCOUNT_LOCALES),
        lifecycleState: readRequiredEnumValue(record['lifecycle_state'], 'Messaging account lifecycle_state', MESSAGING_ACCOUNT_STATES),
        revision: readRequiredFiniteIntegerValue(record['revision'], 'Messaging account revision'),
        lifecycleGeneration: readRequiredFiniteIntegerValue(record['lifecycle_generation'], 'Messaging account lifecycle_generation'),
        plaintextSecretRepliesEnabled: readRequiredBooleanValue(record['plaintext_secret_replies_enabled'], 'Messaging account plaintext_secret_replies_enabled'),
        acceptMessagesFromAnyone: readRequiredBooleanValue(record['accept_messages_from_anyone'], 'Messaging account accept_messages_from_anyone'),
        installedCallbackFingerprint: readNullableTrimmedStringValue(record['installed_callback_fingerprint'], 'Messaging account installed_callback_fingerprint'),
        callbackOwnershipState: readRequiredEnumValue(record['callback_ownership_state'], 'Messaging account callback_ownership_state', MESSAGING_CALLBACK_OWNERSHIP_STATES),
        healthCode: readNullableTrimmedStringValue(record['health_code'], 'Messaging account health_code'),
        healthCheckedAtMs: healthCheckedAt === null || healthCheckedAt === undefined ? null : readRequiredFiniteIntegerValue(healthCheckedAt, 'Messaging account health_checked_at_ms'),
        createdAtMs: readRequiredFiniteIntegerValue(record['created_at_ms'], 'Messaging account created_at_ms'),
        updatedAtMs: readRequiredFiniteIntegerValue(record['updated_at_ms'], 'Messaging account updated_at_ms'),
        authorizedSenders: decodeAuthorizedSenders(record['authorized_senders'], 'Messaging account authorized_senders')
    };
};

const decodeMessagingAccounts = (value: ApiResponsePayload): MessagingAccount[] => {
    if (!Array.isArray(value)) throw new TypeError('Messaging accounts response must be an array');
    return value.map((entry) => decodeMessagingAccount(entry));
};

const decodeMessagingMcpCatalog = (value: ApiResponsePayload): McpFormCatalog => {
    const record = requireRecord(value, 'Messaging MCP catalog');
    return {
        tools: parseMcpToolList(record),
        defaultTools: readRequiredTrimmedStringArrayValue(record['default_tools'], 'Messaging MCP catalog default_tools'),
        planTools: readRequiredTrimmedStringArrayValue(record['plan_tools'], 'Messaging MCP catalog plan_tools'),
        executeTools: readRequiredTrimmedStringArrayValue(record['execute_tools'], 'Messaging MCP catalog execute_tools')
    };
};

const serializeMessagingCredentials = (credentials: MessagingCredentials): JsonObject => {
    if (credentials.platform === 'telegram') return { 'bot_token': credentials.botToken, 'webhook_secret': credentials.webhookSecret };
    if (credentials.platform === 'discord') return { 'bot_token': credentials.botToken, 'application_id': credentials.applicationId };
    return {
        'access_token': credentials.accessToken,
        'phone_number_id': credentials.phoneNumberId,
        'business_account_id': credentials.businessAccountId,
        'application_id': credentials.applicationId,
        'api_version': credentials.apiVersion,
        'app_secret': credentials.appSecret,
        'verify_token': credentials.verifyToken
    };
};

export { decodeMessagingAccount, decodeMessagingAccounts, decodeMessagingMcpCatalog, serializeMessagingCredentials };
export type { DiscordMessagingCredentials, MessagingAccount, MessagingAccountCreate, MessagingAccountLifecycleState, MessagingAccountLocale, MessagingAccountUpdate, MessagingAuthorizedSender, MessagingCallbackOwnershipState, MessagingCredentials, MessagingPlatform, TelegramMessagingCredentials, WhatsAppMessagingCredentials };
