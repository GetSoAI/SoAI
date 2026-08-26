/* SoAI - V1 chat preference pending-intent journal [frontend/assets/ts/core/storage/chatpreferences/chatPreferencePendingJournal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { stableJsonStringify } from '@core/serialization/json.ts';
import { isUnicodeScalarText } from '@core/primitives/text.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { createStorageDefaults } from '@core/storage/defaults.ts';
import { serializeChatCache } from '@core/storage/persistence/chatPreferenceSerialization.ts';
import { decodeConversationDefaultDelta } from '@core/chat/conversationDefaultPreferences.ts';
import { CHAT_WIRE_TO_PARAMETER_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import { getParameterMeta } from '@core/chat/parameters/chatParameterMeta.ts';
import { isChatMobileAuxiliaryAction } from '@core/chat/parameters/mobileAuxiliaryAction.ts';
import { isReasoningEffortLevel } from '@core/chat/parameters/reasoningEffort.ts';
import { isChatServiceTier } from '@core/chat/parameters/serviceTier.ts';

const CHAT_PREFERENCE_PENDING_JOURNAL_VERSION = 1;
const CHAT_PREFERENCE_PENDING_JOURNAL_MAX_BYTES = 64 * 1024;
const JOURNAL_KEYS = Object.freeze(['version', 'user_id', 'window_id', 'chat_delta', 'conversation_defaults_delta']);
const SORTED_JOURNAL_KEYS = Object.freeze([...JOURNAL_KEYS].sort((left, right) => left.localeCompare(right, 'en')));

type ChatPreferencePendingJournal = Readonly<{
    version: 1;
    userId: string;
    windowId: string;
    chatDelta: JsonObject;
    conversationDefaultsDelta: JsonObject;
}>;

const hasExactKeys = (record: JsonObject): boolean => {
    const actual = Object.keys(record).sort((left, right) => left.localeCompare(right, 'en'));
    return actual.length === SORTED_JOURNAL_KEYS.length && actual.every((key, index) => key === SORTED_JOURNAL_KEYS[index]);
};

const journalStorageKey = (userId: string): string => `soai.webui.chat-preference-pending-v1:${encodeURIComponent(userId)}`;

const validParameterValue = (wireKey: string, value: JsonValue, template: JsonValue): boolean => {
    const parameterKey = CHAT_WIRE_TO_PARAMETER_KEYS[wireKey] ?? wireKey;
    if (value === null) return template === null;
    if (parameterKey === 'reasoningEffort') return typeof value === 'string' && isReasoningEffortLevel(value);
    if (parameterKey === 'serviceTier') return typeof value === 'string' && isChatServiceTier(value);
    if (parameterKey === 'inputActionMobileAuxiliaryAction') return typeof value === 'string' && isChatMobileAuxiliaryAction(value);
    if (parameterKey === 'stop') return Array.isArray(value) && value.length <= 50 && value.every((entry) => typeof entry === 'string' && isUnicodeScalarText(entry));
    if (parameterKey === 'voiceTtsSpeed') return typeof value === 'number' && Number.isFinite(value);
    const meta = getParameterMeta(parameterKey);
    if (meta?.type === 'number') {
        if (typeof value !== 'number' || !Number.isFinite(value) || (meta.min !== undefined && value < meta.min) || (meta.max !== undefined && value > meta.max)) return false;
        if (meta.precision === 0 && !Number.isSafeInteger(value)) return false;
        return parameterKey !== 'maxCompletionTokens' || value <= 4_194_304;
    }
    if (Array.isArray(template)) return Array.isArray(value) && value.every((entry) => typeof entry === 'string' && isUnicodeScalarText(entry));
    if (typeof template === 'string') return typeof value === 'string' && isUnicodeScalarText(value);
    return typeof value === typeof template;
};

const validSparseValue = (value: JsonValue, template: JsonValue, path: readonly string[], allowEmptyObjects: boolean): boolean => {
    if (isJsonObject(template)) {
        if (!isJsonObject(value) || (!allowEmptyObjects && path.length > 0 && Object.keys(value).length === 0)) return false;
        return Object.entries(value).every(([key, entry]) => {
            const templateValue = template[key];
            return templateValue !== undefined && validSparseValue(entry, templateValue, [...path, key], allowEmptyObjects);
        });
    }
    if (path.length >= 2 && path[path.length - 2] === 'parameters') {
        const parameterKey = path[path.length - 1];
        return parameterKey !== undefined && validParameterValue(parameterKey, value, template);
    }
    if (Array.isArray(template)) {
        return Array.isArray(value) && value.every((entry) => typeof entry === 'string' && isUnicodeScalarText(entry));
    }
    const leaf = path[path.length - 1];
    if (leaf === 'text_zoom') return typeof value === 'number' && Number.isFinite(value) && value >= 0.5 && value <= 1.5;
    if (template === null) {
        if (value === null) return true;
        return typeof value === 'string' && isUnicodeScalarText(value);
    }
    if (typeof template === 'number') return typeof value === 'number' && Number.isFinite(value);
    if (typeof template === 'string') return typeof value === 'string' && isUnicodeScalarText(value);
    return typeof value === typeof template;
};

const isSupportedChatPreferenceDelta = (value: JsonObject, allowEmptyObjects = false): boolean => validSparseValue(value, serializeChatCache(createStorageDefaults().chat), [], allowEmptyObjects);

const decodeChatPreferencePendingJournal = (value: JsonValue, userId: string, windowId: string): ChatPreferencePendingJournal | null => {
    if (new TextEncoder().encode(stableJsonStringify(value)).byteLength > CHAT_PREFERENCE_PENDING_JOURNAL_MAX_BYTES) return null;
    if (!isJsonObject(value) || !hasExactKeys(value) || value['version'] !== CHAT_PREFERENCE_PENDING_JOURNAL_VERSION || value['user_id'] !== userId || value['window_id'] !== windowId || !isJsonObject(value['chat_delta']) || !isJsonObject(value['conversation_defaults_delta']) || !isSupportedChatPreferenceDelta(value['chat_delta']) || decodeConversationDefaultDelta(value['conversation_defaults_delta']) === null) return null;
    return { version: 1, userId, windowId, chatDelta: value['chat_delta'], conversationDefaultsDelta: value['conversation_defaults_delta'] };
};

const serializeChatPreferencePendingJournal = (journal: ChatPreferencePendingJournal): JsonObject => {
    if (!journal.userId || !journal.windowId || !isUnicodeScalarText(journal.userId) || !isUnicodeScalarText(journal.windowId) || !isSupportedChatPreferenceDelta(journal.chatDelta) || decodeConversationDefaultDelta(journal.conversationDefaultsDelta) === null) {
        throw new Error('Chat preference pending journal is invalid.');
    }
    const record: JsonObject = { version: CHAT_PREFERENCE_PENDING_JOURNAL_VERSION, 'user_id': journal.userId, 'window_id': journal.windowId, 'chat_delta': journal.chatDelta, 'conversation_defaults_delta': journal.conversationDefaultsDelta };
    const serialized = stableJsonStringify(record);
    if (new TextEncoder().encode(serialized).byteLength > CHAT_PREFERENCE_PENDING_JOURNAL_MAX_BYTES) throw new Error('Chat preference pending journal exceeds 64 KiB.');
    return record;
};

export { decodeChatPreferencePendingJournal, isSupportedChatPreferenceDelta, journalStorageKey, serializeChatPreferencePendingJournal };
export type { ChatPreferencePendingJournal };
