/* SoAI - Frontend conversation WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/conversationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import { decodeMessage, type WebuiConversationMessageResponse } from '@core/api/contracts/webuiMessageContracts.ts';
import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { hasOwn, isBoolean, isString } from '@core/typeGuards.ts';
import { readRequiredFiniteNumberValue, readRequiredNonNegativeIntegerValue, readRequiredPositiveIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

interface ConversationEventBase {
    eventId: string;
    timestamp: number;
    userId: number;
    convId: string;
}
interface ConversationCreatedEvent extends ConversationEventBase {
    title: string;
    createdAtMs: number;
    lastModifiedAtMs: number;
    isFavorite: boolean;
    color: string | null;
    isAutomation: boolean;
    isMessaging: boolean;
    messagingPlatform: string | null;
    messagingAccountLabel: string | null;
    messagingAccountSnapshotId: string | null;
    settingsAuthority: OpaqueJsonObject | null;
    isArchived: boolean;
}
interface ConversationUpdatedEvent extends ConversationEventBase {
    lastModifiedAtMs: number;
    title?: string;
    isFavorite?: boolean;
    color?: string | null;
    modelSettings?: OpaqueJsonObject;
    isArchived?: boolean;
    messageCount?: number;
    settingsAuthorityChanged: boolean;
}
type ConversationDeletedEvent = ConversationEventBase;
interface MessageSavedEvent extends ConversationEventBase {
    messageCount: number;
    lastModifiedAtMs: number;
    message: WebuiConversationMessageResponse | null;
}

const decodeBase = (payload: JsonValue): ConversationEventBase => {
    const record = requireRecord(payload, 'Conversation event');
    const timestamp = readRequiredFiniteNumberValue(record['timestamp'], 'Conversation event.timestamp');
    if (timestamp <= 0) throw new TypeError('Conversation event.timestamp must be positive');
    return { eventId: readRequiredTrimmedStringValue(record['event_id'], 'Conversation event.event_id'), timestamp, userId: readRequiredPositiveIntegerValue(record['user_id'], 'Conversation event.user_id'), convId: readRequiredTrimmedStringValue(record['conv_id'], 'Conversation event.conv_id') };
};

const decodeCreated = (payload: JsonValue): ConversationCreatedEvent => {
    const record = requireRecord(payload, 'Conversation created event');
    const authority = record['settings_authority'];
    return {
        ...decodeBase(payload),
        title: readRequiredTrimmedStringValue(record['title'], 'Conversation created event.title'),
        createdAtMs: readRequiredPositiveIntegerValue(record['created_at_ms'], 'Conversation created event.created_at_ms'),
        lastModifiedAtMs: readRequiredPositiveIntegerValue(record['last_modified_at_ms'], 'Conversation created event.last_modified_at_ms'),
        isFavorite: readRequiredBooleanValue(record['is_favorite'], 'Conversation created event.is_favorite'),
        color: readNullableTrimmedStringValue(record['color'], 'Conversation created event.color'),
        isAutomation: readRequiredBooleanValue(record['is_automation'], 'Conversation created event.is_automation'),
        isMessaging: readRequiredBooleanValue(record['is_messaging'], 'Conversation created event.is_messaging'),
        messagingPlatform: readNullableTrimmedStringValue(record['messaging_platform'], 'Conversation created event.messaging_platform'),
        messagingAccountLabel: readNullableTrimmedStringValue(record['messaging_account_label'], 'Conversation created event.messaging_account_label'),
        messagingAccountSnapshotId: readNullableTrimmedStringValue(record['messaging_account_snapshot_id'], 'Conversation created event.messaging_account_snapshot_id'),
        settingsAuthority: authority === null || authority === undefined ? null : requireRecord(authority, 'Conversation created event.settings_authority'),
        isArchived: readRequiredBooleanValue(record['is_archived'], 'Conversation created event.is_archived')
    };
};

const decodeUpdated = (payload: JsonValue): ConversationUpdatedEvent => {
    const record = requireRecord(payload, 'Conversation updated event');
    const decoded: ConversationUpdatedEvent = { ...decodeBase(payload), lastModifiedAtMs: readRequiredPositiveIntegerValue(record['last_modified_at_ms'], 'Conversation updated event.last_modified_at_ms'), settingsAuthorityChanged: readRequiredBooleanValue(record['settings_authority_changed'], 'Conversation updated event.settings_authority_changed') };
    if (record['title'] !== null && record['title'] !== undefined) decoded.title = readRequiredTrimmedStringValue(record['title'], 'Conversation updated event.title');
    if (isBoolean(record['is_favorite'])) decoded.isFavorite = record['is_favorite'];
    if (record['color_present'] === true) {
        const color = record['color'];
        if (color !== null && !isString(color)) throw new TypeError('Conversation updated event.color must be a string or null');
        decoded.color = color === null ? null : color.trim();
    }
    if (record['model_settings'] !== null && record['model_settings'] !== undefined) decoded.modelSettings = requireRecord(record['model_settings'], 'Conversation updated event.model_settings');
    if (isBoolean(record['is_archived'])) decoded.isArchived = record['is_archived'];
    if (hasOwn(record, 'message_count')) decoded.messageCount = readRequiredNonNegativeIntegerValue(record['message_count'], 'Conversation updated event.message_count');
    return decoded;
};

const decodeDeleted = (payload: JsonValue): ConversationDeletedEvent => decodeBase(payload);

const decodeMessageSaved = (payload: JsonValue): MessageSavedEvent => {
    const record = requireRecord(payload, 'Message saved event');
    const message = record['message'];
    return { ...decodeBase(payload), messageCount: readRequiredNonNegativeIntegerValue(record['message_count'], 'Message saved event.message_count'), lastModifiedAtMs: readRequiredPositiveIntegerValue(record['last_modified_at_ms'], 'Message saved event.last_modified_at_ms'), message: message === null || message === undefined ? null : decodeMessage(message, 'Message saved event.message') };
};

const CONVERSATION_EVENT_CONTRACTS = Object.freeze({
    created: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.CONVERSATION_CREATED, decodeCreated),
    updated: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.CONVERSATION_UPDATED, decodeUpdated),
    deleted: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.CONVERSATION_DELETED, decodeDeleted),
    messageSaved: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.MESSAGE_SAVED, decodeMessageSaved)
});

export { CONVERSATION_EVENT_CONTRACTS };
export type { ConversationCreatedEvent, ConversationDeletedEvent, ConversationEventBase, ConversationUpdatedEvent, MessageSavedEvent };
