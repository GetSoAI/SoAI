/* SoAI - Conversation attention snapshot contracts [frontend/assets/ts/core/chat/conversationAttentionSnapshot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatConversationTerminalIndicator } from '@core/chat/protocols.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isNumber, isObject, isString } from '@core/typeGuards.ts';

type ConversationAttentionEntry = JsonObject & {
    attentionId: number;
    assistantAtMs: number;
    conversationId: string;
    terminalStatus: ChatConversationTerminalIndicator;
};

type ConversationAttentionResource = JsonObject & {
    conversations: ConversationAttentionEntry[];
};

const decodeConversationAttentionSnapshot = (payload: JsonValue | null): ConversationAttentionEntry[] => {
    if (!isObject(payload) || !isArray(payload['conversations'])) {
        throw new TypeError('Conversation attention snapshot must contain conversations');
    }
    return decodeConversationAttentionEntries(payload['conversations'], (value) => decodeConversationAttentionEntry(value['attention_id'], value['assistant_at_ms'], value['conversation_id'], value['terminal_status']));
};

const decodeConversationAttentionResourceValue = (payload: JsonValue | null): ConversationAttentionResource => {
    if (!isObject(payload) || !isArray(payload['conversations'])) {
        throw new TypeError('Conversation attention resource must contain conversations');
    }
    return {
        conversations: decodeConversationAttentionEntries(payload['conversations'], (value) => decodeConversationAttentionEntry(value['attentionId'], value['assistantAtMs'], value['conversationId'], value['terminalStatus']))
    };
};

const decodeConversationAttentionEntries = (values: readonly JsonValue[], decodeEntry: (value: JsonObject) => ConversationAttentionEntry): ConversationAttentionEntry[] => {
    const entries: ConversationAttentionEntry[] = [];
    const conversationIds = new Set<string>();
    for (const value of values) {
        if (!isObject(value)) throw new TypeError('Conversation attention entry must be an object');
        const entry = decodeEntry(value);
        if (conversationIds.has(entry.conversationId)) {
            throw new TypeError('Conversation attention snapshot contains duplicate conversations');
        }
        conversationIds.add(entry.conversationId);
        entries.push(entry);
    }
    return entries;
};

const decodeConversationAttentionEntry = (attentionId: JsonValue | undefined, assistantAtMs: JsonValue | undefined, conversationId: JsonValue | undefined, terminalStatus: JsonValue | undefined): ConversationAttentionEntry => {
    if (!isNumber(attentionId) || !Number.isSafeInteger(attentionId) || attentionId <= 0) {
        throw new TypeError('Conversation attention id must be a positive safe integer');
    }
    if (!isNumber(assistantAtMs) || !Number.isSafeInteger(assistantAtMs) || assistantAtMs <= 0) {
        throw new TypeError('Conversation attention assistant timestamp must be a positive safe integer');
    }
    if (!isString(conversationId) || !conversationId.trim()) {
        throw new TypeError('Conversation attention conversation id must be non-empty');
    }
    if (terminalStatus !== 'complete' && terminalStatus !== 'error') {
        throw new TypeError('Conversation attention terminal status is invalid');
    }
    return { attentionId, assistantAtMs, conversationId: conversationId.trim(), terminalStatus };
};

const decodeConversationAttentionResource = (payload: JsonValue | null): ConversationAttentionResource => ({
    conversations: decodeConversationAttentionSnapshot(payload)
});

export { decodeConversationAttentionResource, decodeConversationAttentionResourceValue, decodeConversationAttentionSnapshot };
export type { ConversationAttentionEntry, ConversationAttentionResource };
