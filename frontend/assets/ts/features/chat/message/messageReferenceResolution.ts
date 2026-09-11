/* SoAI - Chat feature message reference resolution [frontend/assets/ts/features/chat/message/messageReferenceResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNullOrUndefined } from '@core/typeGuards.ts';
import { resolveAssistantVariantIdentity } from '@core/chat/assistantIdentity.ts';
import { formatAssistantVariantIdentityKey, resolveAssistantVariantMessageIndex } from '@features/chat/message/assistantMessageIdentity.ts';
import { resolveAssistantVariantMessageIdentifier, resolveIndexedMessageDomPosition, resolvePersistedMessageIdentifier } from '@features/chat/message/messageDomIds.ts';
import { buildPersistedMessageCursorKey, resolveFallbackMessagePersistenceKey, resolvePersistedMessageCursor } from '@features/chat/message/persistedMessageIdentity.ts';
import type { ChatMessage, ConversationContract, ConversationMessage } from '@features/chat/ChatTypes.ts';

interface ResolvedMessageReference {
    index: number;
    message: ChatMessage | null;
}

type MessageReferenceResolver = (conversation: ConversationContract | null, messageId: string) => ResolvedMessageReference;

type AssistantVariantReferenceIndex = ReadonlyMap<string, ConversationMessage>;

interface IndexedAssistantVariantReference {
    matchedIdentifier: boolean;
    message: ConversationMessage | null;
}

type CapturedMessageReferenceIdentity = {
    originalMessage: ChatMessage;
    persistedCursorKey: string | null;
    fallbackKey: string | null;
};

const captureMessageReferenceIdentity = (message: ChatMessage): CapturedMessageReferenceIdentity => {
    const cursor = resolvePersistedMessageCursor(message);
    return {
        originalMessage: message,
        persistedCursorKey: cursor === null ? null : buildPersistedMessageCursorKey(cursor),
        fallbackKey: cursor === null ? resolveFallbackMessagePersistenceKey(message) : null
    };
};

const resolveMessageReferenceFromIdentity = (conversation: ConversationContract, identity: CapturedMessageReferenceIdentity, isMessageContract: (value: ConversationMessage) => value is ChatMessage): ResolvedMessageReference => {
    const objectIndex = conversation.messages.indexOf(identity.originalMessage);
    if (objectIndex >= 0) {
        return resolveIndexedReference(conversation, objectIndex, isMessageContract);
    }
    let resolved: ResolvedMessageReference | null = null;
    for (let index = 0; index < conversation.messages.length; index += 1) {
        const message = conversation.messages[index];
        if (message === undefined || !isMessageContract(message)) {
            continue;
        }
        const cursor = resolvePersistedMessageCursor(message);
        const matchesCursor = identity.persistedCursorKey !== null && cursor !== null && buildPersistedMessageCursorKey(cursor) === identity.persistedCursorKey;
        const matchesFallback = identity.persistedCursorKey === null && identity.fallbackKey !== null && resolveFallbackMessagePersistenceKey(message) === identity.fallbackKey;
        if (!matchesCursor && !matchesFallback) {
            continue;
        }
        if (resolved !== null) {
            return { index: -1, message: null };
        }
        resolved = { index, message };
    }
    return resolved ?? { index: -1, message: null };
};

const createAssistantVariantReferenceIndex = (conversation: ConversationContract): AssistantVariantReferenceIndex => {
    const index = new Map<string, ConversationMessage>();
    for (const entry of conversation.messages) {
        if (!entry || entry.role !== 'assistant') {
            continue;
        }
        const identity = resolveAssistantVariantIdentity({ assistantTurnTimestamp: entry.assistantTurnAtMs, modelVariantIndex: entry.modelVariantIndex });
        if (identity === null) {
            continue;
        }
        const referenceKey = formatAssistantVariantIdentityKey(identity);
        if (!index.has(referenceKey)) {
            index.set(referenceKey, entry);
        }
    }
    return index;
};

const resolveAssistantVariantReferenceFromIndex = (index: AssistantVariantReferenceIndex, messageId: string): IndexedAssistantVariantReference => {
    const identity = resolveAssistantVariantMessageIdentifier(messageId);
    if (identity === null) {
        return { matchedIdentifier: false, message: null };
    }
    const referenceKey = formatAssistantVariantIdentityKey(identity);
    return {
        matchedIdentifier: true,
        message: index.get(referenceKey) ?? null
    };
};

const resolveIndexedReference = (conversation: ConversationContract, index: number, isMessageContract: (value: ConversationMessage) => value is ChatMessage): ResolvedMessageReference => {
    if (index < 0 || index >= conversation.messages.length) {
        return { index: -1, message: null };
    }
    const entry = conversation.messages[index];
    if (entry === undefined) {
        return { index: -1, message: null };
    }
    return {
        index,
        message: isMessageContract(entry) ? entry : null
    };
};

export const resolveMessageReferenceFromConversation = (conversation: ConversationContract | null, messageId: string, isMessageContract: (value: ConversationMessage) => value is ChatMessage): ResolvedMessageReference => {
    if (!conversation) {
        return { index: -1, message: null };
    }

    const assistantVariantIdentity = resolveAssistantVariantMessageIdentifier(messageId);
    if (assistantVariantIdentity !== null) {
        const indexByIdentity = resolveAssistantVariantMessageIndex(conversation.messages, assistantVariantIdentity);
        if (indexByIdentity !== null) {
            return resolveIndexedReference(conversation, indexByIdentity, isMessageContract);
        }
    }

    const persistedMessageId = resolvePersistedMessageIdentifier(messageId);
    if (persistedMessageId !== null) {
        const indexById = conversation.messages.findIndex((entry) => {
            if (!entry || isNullOrUndefined(entry.id)) {
                return false;
            }
            return String(entry.id) === persistedMessageId;
        });
        if (indexById !== -1) {
            return resolveIndexedReference(conversation, indexById, isMessageContract);
        }
    }

    const numericIndex = resolveIndexedMessageDomPosition(messageId);

    if (numericIndex !== null && numericIndex < conversation.messages.length) {
        const resolved = resolveIndexedReference(conversation, numericIndex, isMessageContract);
        if (resolved.message !== null) {
            return resolved;
        }
    }

    return { index: -1, message: null };
};

export { captureMessageReferenceIdentity, createAssistantVariantReferenceIndex, resolveAssistantVariantReferenceFromIndex, resolveMessageReferenceFromIdentity };
export type { AssistantVariantReferenceIndex, CapturedMessageReferenceIdentity, MessageReferenceResolver, ResolvedMessageReference };
