/* SoAI - Frontend WebUI conversation message envelope contracts [frontend/assets/ts/core/api/contracts/webuiMessageEnvelopeContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { decodeMessageArray } from '@core/api/contracts/webuiMessageContracts.ts';
import { readRequiredEpochMsValue } from '@core/types/payloadValueReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { isJsonArray, type JsonValue } from '@core/types/jsonValues.ts';
import type { ConversationMessageSyncCursorResponse, ConversationMessageWindowResponse, ConversationMessageWriteResponse, ConversationRunningActivityResponse, MessageCursorResponse } from '@core/api/contracts/webuiConversationContracts.ts';

const readCount = (value: JsonValue | undefined, label: string): number => {
    if (typeof value !== 'number' || !Number.isInteger(value) || value < 0) throw new TypeError(`${label} must be a non-negative integer.`);
    return value;
};

const decodeCursor = (value: JsonValue, label: string): MessageCursorResponse => {
    const record = requireRecord(value, label);
    return { createdAtMs: readRequiredEpochMsValue(record['created_at_ms'], `${label}.created_at_ms`), id: readCount(record['id'], `${label}.id`) };
};

const decodeNullableCursor = (value: JsonValue | undefined, label: string): MessageCursorResponse | null =>
    value === null
        ? null
        : value === undefined
          ? (() => {
                throw new TypeError(`${label} is required.`);
            })()
          : decodeCursor(value, label);

const decodeMessageWriteResponse = (value: ApiResponsePayload): ConversationMessageWriteResponse => {
    const record = requireRecord(value, 'Conversation message write response');
    return { lastModifiedAtMs: readRequiredEpochMsValue(record['last_modified_at_ms'], 'Conversation message write response.last_modified_at_ms'), messageCount: readCount(record['message_count'], 'Conversation message write response.message_count'), messages: decodeMessageArray(record['messages'], 'Conversation message write response.messages') };
};

const decodeMessageWindowResponse = (value: ApiResponsePayload): ConversationMessageWindowResponse => {
    const record = requireRecord(value, 'Conversation message window response');
    const oldest = record['oldest_cursor'];
    const newest = record['newest_cursor'];
    if (typeof record['conv_id'] !== 'string') throw new TypeError('Conversation message window response.conv_id must be a string.');
    if (record['has_older'] !== true && record['has_older'] !== false) throw new TypeError('Conversation message window response.has_older must be a boolean.');
    if (record['has_newer'] !== true && record['has_newer'] !== false) throw new TypeError('Conversation message window response.has_newer must be a boolean.');
    return { convId: record['conv_id'], messages: decodeMessageArray(record['messages'], 'Conversation message window response.messages'), returnedCount: readCount(record['returned_count'], 'Conversation message window response.returned_count'), loadedCountHint: readCount(record['loaded_count_hint'], 'Conversation message window response.loaded_count_hint'), totalCount: readCount(record['total_count'], 'Conversation message window response.total_count'), oldestCursor: decodeNullableCursor(oldest, 'Conversation message window response.oldest_cursor'), newestCursor: decodeNullableCursor(newest, 'Conversation message window response.newest_cursor'), hasOlder: record['has_older'], hasNewer: record['has_newer'], lastModifiedAtMs: readRequiredEpochMsValue(record['last_modified_at_ms'], 'Conversation message window response.last_modified_at_ms') };
};

const decodeRunningActivityResponse = (value: ApiResponsePayload): ConversationRunningActivityResponse => {
    const record = requireRecord(value, 'Conversation running activity response');
    if (typeof record['conv_id'] !== 'string') throw new TypeError('Conversation running activity response.conv_id must be a string.');
    return { convId: record['conv_id'], runningMessages: decodeMessageArray(record['running_messages'], 'Conversation running activity response.running_messages'), lastModifiedAtMs: readRequiredEpochMsValue(record['last_modified_at_ms'], 'Conversation running activity response.last_modified_at_ms') };
};

const decodeMessageSyncCursorResponse = (value: ApiResponsePayload): ConversationMessageSyncCursorResponse => {
    const record = requireRecord(value, 'Conversation message sync cursor response');
    const timestamp = record['timestamp'];
    return { timestamp: timestamp === null ? null : readRequiredEpochMsValue(timestamp, 'Conversation message sync cursor response.timestamp'), lastModifiedAtMs: readRequiredEpochMsValue(record['last_modified_at_ms'], 'Conversation message sync cursor response.last_modified_at_ms'), messageCount: readCount(record['message_count'], 'Conversation message sync cursor response.message_count') };
};

const decodeOptionalJsonObject = (value: JsonValue | undefined, label: string): Record<string, JsonValue> | undefined => {
    if (value === undefined) return undefined;
    if (!isJsonArray(value) && typeof value === 'object' && value !== null) return value;
    throw new TypeError(`${label} must be an object.`);
};

export { decodeMessageSyncCursorResponse, decodeMessageWindowResponse, decodeMessageWriteResponse, decodeOptionalJsonObject, decodeRunningActivityResponse };
