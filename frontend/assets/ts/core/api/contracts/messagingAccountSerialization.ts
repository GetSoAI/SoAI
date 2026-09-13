/* SoAI - Messaging account request serialization [frontend/assets/ts/core/api/contracts/messagingAccountSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { serializeConversationModelSettings } from '@core/chat/executionSettingsMapping.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { serializeMessagingCredentials, type MessagingAccountCreate, type MessagingAccountUpdate, type MessagingAuthorizedSender } from '@core/api/contracts/messagingAccountContracts.ts';

const serializeSender = (sender: MessagingAuthorizedSender): JsonObject => ({
    'sender_id': sender.senderId,
    'display_label': sender.displayLabel
});

const serializeAccountFields = (account: MessagingAccountCreate | MessagingAccountUpdate): JsonObject => ({
    'label': account.label,
    'model_settings': serializeConversationModelSettings(account.modelSettings),
    'locale': account.locale,
    'plaintext_secret_replies_enabled': account.plaintextSecretRepliesEnabled,
    'accept_messages_from_anyone': account.acceptMessagesFromAnyone,
    'replace_existing_callback': account.replaceExistingCallback,
    'authorized_senders': account.authorizedSenders.map(serializeSender)
});

const serializeMessagingAccountCreate = (account: MessagingAccountCreate): JsonObject => ({
    ...serializeAccountFields(account),
    'platform': account.credentials.platform,
    'credentials': serializeMessagingCredentials(account.credentials)
});

const serializeMessagingAccountUpdate = (account: MessagingAccountUpdate): JsonObject => ({
    ...serializeAccountFields(account),
    'expected_revision': account.expectedRevision,
    'enabled': account.enabled,
    'credentials': account.credentials === null ? null : serializeMessagingCredentials(account.credentials)
});

const serializeMessagingAccountLifecycle = (expectedRevision: number, enabled: boolean): JsonObject => ({
    'expected_revision': expectedRevision,
    'enabled': enabled,
    'replace_existing_callback': false
});

export { serializeMessagingAccountCreate, serializeMessagingAccountLifecycle, serializeMessagingAccountUpdate };
