/* SoAI - Frontend WebUI conversation response contracts [frontend/assets/ts/core/api/contracts/webuiConversationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import { isJsonArray, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { WebuiConversationMessageResponse } from '@core/api/contracts/webuiMessageContracts.ts';
import { decodeConversationSettingsAuthority, type ConversationSettingsAuthority } from '@core/chat/conversationSettingsAuthority.ts';
import { decodeConversationSource, type MessagingPlatform } from '@core/chat/conversationSource.ts';

interface WebuiConversationResponse {
    id: string;
    title: string;
    createdAtMs: number;
    lastModifiedAtMs: number;
    modelSettings: JsonObject;
    isFavorite: boolean;
    color: string | null;
    isAutomation: boolean;
    isMessaging: boolean;
    messagingPlatform: MessagingPlatform | null;
    messagingAccountLabel: string | null;
    messagingAccountSnapshotId: string | null;
    isArchived: boolean;
    messageCount: number;
    compactionCount: number;
    compactionTokensSaved: number;
    settingsAuthority: ConversationSettingsAuthority;
}

interface ArchivedConversationResponse {
    id: string;
    title: string;
    lastModifiedAtMs: number;
    color: string | null;
    isFavorite: boolean;
    isAutomation: boolean;
    isMessaging: boolean;
    messagingPlatform: MessagingPlatform | null;
    messagingAccountLabel: string | null;
    messagingAccountSnapshotId: string | null;
    isArchived: true;
    messageCount: number;
    compactionCount: number;
    compactionTokensSaved: number;
    settingsAuthority: ConversationSettingsAuthority;
}

interface ArchivedConversationsPageResponse {
    conversations: ArchivedConversationResponse[];
    totalCount: number;
    nextCursor: { lastModifiedAtMs: number; id: string } | null;
}

interface MessageCursorResponse {
    createdAtMs: number;
    id: number;
}

interface ConversationMessageWriteResponse {
    lastModifiedAtMs: number;
    messageCount: number;
    messages: WebuiConversationMessageResponse[];
}

interface ConversationMessageWindowResponse {
    convId: string;
    messages: WebuiConversationMessageResponse[];
    returnedCount: number;
    loadedCountHint: number;
    totalCount: number;
    oldestCursor: MessageCursorResponse | null;
    newestCursor: MessageCursorResponse | null;
    hasOlder: boolean;
    hasNewer: boolean;
    lastModifiedAtMs: number;
}

interface ConversationRunningActivityResponse {
    convId: string;
    runningMessages: WebuiConversationMessageResponse[];
    lastModifiedAtMs: number;
}

interface ConversationMessageSyncCursorResponse {
    timestamp: number | null;
    lastModifiedAtMs: number;
    messageCount: number;
}

interface ConversationBatchDeleteResponse {
    deleted: number;
    deletedIds: string[];
}

interface ConversationDeleteAllResponse {
    deleted: number;
}

interface ConversationStreamStatusResponse {
    active: boolean;
    conversationId: string;
    startAdmission: 'inactive' | 'busy' | 'unknown';
    streamLifecycle: 'inactive' | 'streaming' | 'terminalizing';
    canAcceptConversationInput: boolean;
    canStartNextPrompt: boolean;
    canAcceptSteerPrompt: boolean;
    activeToolCallCount: number;
    requestId?: string;
    assistantAtMs?: number;
    assistantTurnAtMs?: number;
    modelVariantIndex?: number;
    modelId?: string;
    previewKey?: string;
    previewArguments?: JsonObject;
    previewGeneratedAtMs?: number;
    previewCooldownMs?: number;
    previewTrigger?: string;
}

const readEpochMs = (record: JsonObject, key: string, label: string): number => readRequiredNonNegativeIntegerValue(record[key], `${label}.${key}`);

const decodeConversationRecord = (value: JsonValue, label: string): WebuiConversationResponse => {
    const record = requireRecord(value, label);
    const source = decodeConversationSource(record, label);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        title: readRequiredTrimmedString(record, 'title', `${label}.title`),
        createdAtMs: readEpochMs(record, 'created_at_ms', label),
        lastModifiedAtMs: readEpochMs(record, 'last_modified_at_ms', label),
        modelSettings: requireRecord(record['model_settings'], `${label}.model_settings`),
        isFavorite: readRequiredBooleanValue(record['is_favorite'], `${label}.is_favorite`),
        color: readNullableTrimmedStringValue(record['color'], `${label}.color`),
        isAutomation: readRequiredBooleanValue(record['is_automation'], `${label}.is_automation`),
        ...source,
        isArchived: readRequiredBooleanValue(record['is_archived'], `${label}.is_archived`),
        messageCount: readRequiredNonNegativeIntegerValue(record['message_count'], `${label}.message_count`),
        compactionCount: readRequiredNonNegativeIntegerValue(record['compaction_count'], `${label}.compaction_count`),
        compactionTokensSaved: readRequiredNonNegativeIntegerValue(record['compaction_tokens_saved'], `${label}.compaction_tokens_saved`),
        settingsAuthority: decodeConversationSettingsAuthority(record['settings_authority'], `${label}.settings_authority`)
    };
};

const decodeConversationResponse = (value: ApiResponsePayload): WebuiConversationResponse => decodeConversationRecord(requireRecord(value, 'Conversation response'), 'Conversation response');

const decodeConversationListResponse = (value: ApiResponsePayload): WebuiConversationResponse[] => {
    if (!isJsonArray(value)) throw new TypeError('Conversation list response must be an array.');
    return value.map((entry, index) => decodeConversationRecord(entry, `Conversation list response[${String(index)}]`));
};

const decodeArchivedConversationRecord = (value: JsonValue, label: string): ArchivedConversationResponse => {
    const record = requireRecord(value, label);
    const source = decodeConversationSource(record, label);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        title: readRequiredTrimmedString(record, 'title', `${label}.title`),
        lastModifiedAtMs: readEpochMs(record, 'last_modified_at_ms', label),
        color: readNullableTrimmedStringValue(record['color'], `${label}.color`),
        isFavorite: readRequiredBooleanValue(record['is_favorite'], `${label}.is_favorite`),
        isAutomation: readRequiredBooleanValue(record['is_automation'], `${label}.is_automation`),
        ...source,
        isArchived: true,
        messageCount: readRequiredNonNegativeIntegerValue(record['message_count'], `${label}.message_count`),
        compactionCount: readRequiredNonNegativeIntegerValue(record['compaction_count'], `${label}.compaction_count`),
        compactionTokensSaved: readRequiredNonNegativeIntegerValue(record['compaction_tokens_saved'], `${label}.compaction_tokens_saved`),
        settingsAuthority: decodeConversationSettingsAuthority(record['settings_authority'], `${label}.settings_authority`)
    };
};

const decodeArchivedPageResponse = (value: ApiResponsePayload): ArchivedConversationsPageResponse => {
    const record = requireRecord(value, 'Archived conversations response');
    const conversations = record['conversations'];
    if (!isJsonArray(conversations)) throw new TypeError('Archived conversations response.conversations must be an array.');
    const cursor = record['next_cursor'];
    const nextCursor =
        cursor === null
            ? null
            : (() => {
                  const cursorRecord = requireRecord(cursor, 'Archived conversations response.next_cursor');
                  return { lastModifiedAtMs: readEpochMs(cursorRecord, 'last_modified_at_ms', 'Archived conversations response.next_cursor'), id: readRequiredTrimmedString(cursorRecord, 'id', 'Archived conversations response.next_cursor.id') };
              })();
    return { conversations: conversations.map((entry, index) => decodeArchivedConversationRecord(entry, `Archived conversations response.conversations[${String(index)}]`)), totalCount: readRequiredNonNegativeIntegerValue(record['total_count'], 'Archived conversations response.total_count'), nextCursor };
};

const decodeArchivedSearchResponse = (value: ApiResponsePayload): ArchivedConversationResponse[] => {
    const record = requireRecord(value, 'Archived conversation search response');
    const conversations = record['conversations'];
    if (!isJsonArray(conversations)) throw new TypeError('Archived conversation search response.conversations must be an array.');
    return conversations.map((entry, index) => decodeArchivedConversationRecord(entry, `Archived conversation search response.conversations[${String(index)}]`));
};

const decodeConversationBatchDeleteResponse = (value: ApiResponsePayload): ConversationBatchDeleteResponse => {
    const record = requireRecord(value, 'Conversation batch delete response');
    const deletedIds = record['deleted_ids'];
    if (!isJsonArray(deletedIds)) throw new TypeError('Conversation batch delete response.deleted_ids must be an array of strings.');
    const normalizedIds: string[] = [];
    for (const entry of deletedIds) {
        if (typeof entry !== 'string') throw new TypeError('Conversation batch delete response.deleted_ids must be an array of strings.');
        normalizedIds.push(entry);
    }
    return { deleted: readRequiredNonNegativeIntegerValue(record['deleted'], 'Conversation batch delete response.deleted'), deletedIds: normalizedIds };
};

const decodeConversationDeleteAllResponse = (value: ApiResponsePayload): ConversationDeleteAllResponse => {
    const record = requireRecord(value, 'Conversation delete all response');
    return { deleted: readRequiredNonNegativeIntegerValue(record['deleted'], 'Conversation delete all response.deleted') };
};

const decodeConversationRecordResponse = decodeConversationResponse;

export { decodeArchivedPageResponse, decodeArchivedSearchResponse, decodeConversationBatchDeleteResponse, decodeConversationDeleteAllResponse, decodeConversationListResponse, decodeConversationRecord, decodeConversationRecordResponse, decodeConversationResponse };
export type { ArchivedConversationResponse, ArchivedConversationsPageResponse, ConversationBatchDeleteResponse, ConversationDeleteAllResponse, ConversationMessageSyncCursorResponse, ConversationMessageWindowResponse, ConversationMessageWriteResponse, ConversationRunningActivityResponse, ConversationStreamStatusResponse, MessageCursorResponse, WebuiConversationResponse };
