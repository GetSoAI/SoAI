/* SoAI - Chat stream message conversation mapping [frontend/assets/ts/features/chat/chatstreamservice/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber } from '@core/typeGuards.ts';
import { preserveAssistantCollapsedOverrideRecords } from '@features/chat/assistanteventtimeline/collapsedOverrideRecords.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { requireAssistantMessageVariantIdentity, resolveAssistantVariantMessageIndex } from '@features/chat/message/assistantMessageIdentity.ts';
import { resolveMessageTimestampInsertIndex } from '@features/chat/message/messageTimestampOrdering.ts';
import { isConversationWindowAtTail } from '@features/chat/storage/messageWindowState.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';

type AssistantMessageUpsertResult = { accepted: true; message: ChatMessage; changed: boolean; placement: 'loaded-window' | 'beyond-loaded-window' } | { accepted: false; changed: false };

const prepareAssistantMessageForConversation = (existing: ChatMessage | null, incoming: ChatMessage): ChatMessage => {
    if (existing) {
        preserveAssistantCollapsedOverrideRecords(existing, incoming);
    }
    return incoming;
};

const reconcileAssistantTailForIncomingStream = (messages: ChatMessage[], assistantTurnTimestamp: number, pruneSupersededTail: boolean): boolean => {
    let lastUserIndex = -1;
    for (let index = messages.length - 1; index >= 0; index -= 1) {
        const candidate = messages[index];
        if (candidate?.role === 'user') {
            lastUserIndex = index;
            break;
        }
    }
    if (lastUserIndex < 0) {
        return true;
    }
    const lastUserMessage = messages[lastUserIndex];
    const lastUserTimestamp = lastUserMessage?.timestamp;
    if (!isNumber(lastUserTimestamp) || !Number.isInteger(lastUserTimestamp) || assistantTurnTimestamp <= lastUserTimestamp) {
        return true;
    }
    for (let index = messages.length - 1; index > lastUserIndex; index -= 1) {
        const candidate = messages[index];
        if (candidate?.role === 'assistant' && isNumber(candidate.assistantTurnAtMs) && Number.isInteger(candidate.assistantTurnAtMs) && candidate.assistantTurnAtMs > assistantTurnTimestamp) {
            return false;
        }
    }
    if (!pruneSupersededTail) {
        return true;
    }
    for (let index = messages.length - 1; index > lastUserIndex; index -= 1) {
        const candidate = messages[index];
        if (candidate?.role === 'assistant' && candidate.assistantTurnAtMs !== assistantTurnTimestamp) {
            messages.splice(index, 1);
        }
    }
    return true;
};

const upsertAssistantMessage = (conversation: Conversation, assistantTimestamp: number, message: ChatMessage): AssistantMessageUpsertResult => {
    const messages = conversation.messages;
    if (typeof message.timestamp !== 'number' || !Number.isInteger(message.timestamp) || message.timestamp !== assistantTimestamp) {
        throw new Error('Assistant stream upsert requires message.timestamp to match assistantTimestamp');
    }
    const identity = requireAssistantMessageVariantIdentity(message, 'Assistant stream message');
    const windowAtTail = isConversationWindowAtTail(conversation);
    if (!reconcileAssistantTailForIncomingStream(messages, identity.assistantTurnTimestamp, windowAtTail)) {
        return { accepted: false, changed: false };
    }
    const index = resolveAssistantVariantMessageIndex(messages, identity);
    if (index !== null) {
        const existing = messages[index];
        if (existing === undefined) {
            throw new Error('Assistant stream message index resolved without a message');
        }
        if (existing === message) {
            prepareAssistantMessageForConversation(existing, existing);
            return { accepted: true, message: existing, changed: false, placement: 'loaded-window' };
        }
        const preparedMessage = prepareAssistantMessageForConversation(existing, message);
        messages[index] = preparedMessage;
        return { accepted: true, message: preparedMessage, changed: true, placement: 'loaded-window' };
    }
    const preparedMessage = prepareAssistantMessageForConversation(null, message);
    if (!windowAtTail) {
        return { accepted: true, message: preparedMessage, changed: false, placement: 'beyond-loaded-window' };
    }
    const insertIndex = resolveMessageTimestampInsertIndex(messages, assistantTimestamp);
    messages.splice(insertIndex, 0, preparedMessage);
    return { accepted: true, message: preparedMessage, changed: true, placement: 'loaded-window' };
};

export { upsertAssistantMessage };
