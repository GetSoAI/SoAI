/* SoAI - Chat feature message DOM IDs [frontend/assets/ts/features/chat/message/messageDomIds.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseNonNegativeIntegerFromStringOrNull } from '@core/dom/attributes.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isNumber, isString } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/message/messageSegments.ts';
import { requireAssistantVariantIdentity } from '@core/chat/assistantIdentity.ts';
import { formatAssistantVariantIdentityKey } from '@features/chat/message/assistantMessageIdentity.ts';

const MESSAGE_DOM_ASSISTANT_VARIANT_PREFIX = 'av:';
const MESSAGE_DOM_INDEX_PREFIX = 'idx:';
const MESSAGE_DOM_CONVERSATION_INPUT_PREFIX = 'ci:';
const MESSAGE_DOM_PERSISTED_PREFIX = 'id:';
const CONVERSATION_INPUT_MESSAGE_ID_FIELD = 'soaiConversationInputId';

const normalizeMessageDomId = (messageId: string): string => toTrimmedString(messageId);

const buildAssistantVariantMessageDomId = (assistantTurnTimestamp: number, modelVariantIndex: number): string => {
    const identity = requireAssistantVariantIdentity({ assistantTurnTimestamp, modelVariantIndex, context: 'Assistant message DOM id' });
    return `${MESSAGE_DOM_ASSISTANT_VARIANT_PREFIX}${formatAssistantVariantIdentityKey(identity)}`;
};

const buildIndexedMessageDomId = (index: number): string => {
    if (!Number.isInteger(index) || index < 0) {
        throw new Error('Message DOM index id requires a non-negative integer index');
    }
    return `${MESSAGE_DOM_INDEX_PREFIX}${String(index)}`;
};

const buildConversationInputMessageDomId = (inputId: string): string => {
    const normalizedInputId = toTrimmedString(inputId);
    if (!normalizedInputId) {
        throw new Error('Conversation input message DOM id requires an input id');
    }
    return `${MESSAGE_DOM_CONVERSATION_INPUT_PREFIX}${normalizedInputId}`;
};

const resolveConversationInputMessageIdentifierFromMessage = (message: ChatMessage): string | null => {
    const inputId = message[CONVERSATION_INPUT_MESSAGE_ID_FIELD];
    const normalizedInputId = toTrimmedString(inputId);
    return normalizedInputId ? normalizedInputId : null;
};

const resolveStableMessageDomId = (message: ChatMessage): string | null => {
    if (message.role === 'assistant') {
        const identity = requireAssistantVariantIdentity({
            assistantTurnTimestamp: message.assistantTurnAtMs,
            modelVariantIndex: message.modelVariantIndex,
            context: 'Assistant message DOM id'
        });
        return buildAssistantVariantMessageDomId(identity.assistantTurnTimestamp, identity.modelVariantIndex);
    }
    const rawId = message.id;
    if (isString(rawId) && rawId.trim()) {
        return `${MESSAGE_DOM_PERSISTED_PREFIX}${rawId.trim()}`;
    }
    if (isNumber(rawId) && Number.isFinite(rawId)) {
        return `${MESSAGE_DOM_PERSISTED_PREFIX}${String(rawId)}`;
    }
    const conversationInputId = resolveConversationInputMessageIdentifierFromMessage(message);
    if (conversationInputId !== null) {
        return buildConversationInputMessageDomId(conversationInputId);
    }
    return null;
};

const resolveMessageDomId = (message: ChatMessage, index: number): string => {
    const stableDomId = resolveStableMessageDomId(message);
    if (stableDomId !== null) {
        return stableDomId;
    }
    return buildIndexedMessageDomId(index);
};

const isIndexedToPersistedMessageDomIdUpgrade = (existingDomId: string, nextDomId: string): boolean => {
    return resolveIndexedMessageDomPosition(existingDomId) !== null && resolvePersistedMessageIdentifier(nextDomId) !== null;
};

const resolveAssistantVariantMessageIdentifier = (messageId: string): { assistantTurnTimestamp: number; modelVariantIndex: number } | null => {
    const normalized = normalizeMessageDomId(messageId);
    if (!normalized) {
        return null;
    }
    if (!normalized.startsWith(MESSAGE_DOM_ASSISTANT_VARIANT_PREFIX)) {
        return null;
    }
    const remainder = normalized.slice(MESSAGE_DOM_ASSISTANT_VARIANT_PREFIX.length).trim();
    if (!remainder) {
        return null;
    }
    const parts = remainder.split(':');
    if (parts.length !== 2) {
        return null;
    }
    const assistantTurnText = parts[0] ? parts[0].trim() : '';
    const variantText = parts[1] ? parts[1].trim() : '';
    if (!assistantTurnText || !variantText) {
        return null;
    }
    const assistantTurnTimestamp = parseNonNegativeIntegerFromStringOrNull(assistantTurnText);
    if (assistantTurnTimestamp === null || assistantTurnTimestamp <= 0) {
        return null;
    }
    const modelVariantIndex = parseNonNegativeIntegerFromStringOrNull(variantText);
    if (modelVariantIndex === null) {
        return null;
    }
    return { assistantTurnTimestamp, modelVariantIndex };
};

const resolvePersistedMessageIdentifier = (messageId: string): string | null => {
    const normalized = normalizeMessageDomId(messageId);
    if (!normalized) {
        return null;
    }
    if (!normalized.startsWith(MESSAGE_DOM_PERSISTED_PREFIX)) {
        return null;
    }
    const persistedId = normalized.slice(MESSAGE_DOM_PERSISTED_PREFIX.length).trim();
    if (!persistedId) {
        return null;
    }
    return persistedId;
};

const resolveConversationInputMessageIdentifier = (messageId: string): string | null => {
    const normalized = normalizeMessageDomId(messageId);
    if (!normalized) {
        return null;
    }
    if (!normalized.startsWith(MESSAGE_DOM_CONVERSATION_INPUT_PREFIX)) {
        return null;
    }
    const inputId = normalized.slice(MESSAGE_DOM_CONVERSATION_INPUT_PREFIX.length).trim();
    if (!inputId) {
        return null;
    }
    return inputId;
};

const resolveIndexedMessageDomPosition = (messageId: string): number | null => {
    const normalized = normalizeMessageDomId(messageId);
    if (!normalized) {
        return null;
    }
    if (!normalized.startsWith(MESSAGE_DOM_INDEX_PREFIX)) {
        return null;
    }
    const indexText = normalized.slice(MESSAGE_DOM_INDEX_PREFIX.length).trim();
    if (!indexText) {
        return null;
    }
    return parseNonNegativeIntegerFromStringOrNull(indexText);
};

export { normalizeMessageDomId, resolveAssistantVariantMessageIdentifier, resolveIndexedMessageDomPosition, resolveMessageDomId, resolveConversationInputMessageIdentifier, resolveConversationInputMessageIdentifierFromMessage, resolvePersistedMessageIdentifier };
export { resolveStableMessageDomId };
export { buildAssistantVariantMessageDomId, buildConversationInputMessageDomId };
export { isIndexedToPersistedMessageDomIdUpgrade };
export { CONVERSATION_INPUT_MESSAGE_ID_FIELD };
