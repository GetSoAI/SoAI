/* SoAI - Optimistic local user message mount for immediately dispatched conversation inputs [frontend/assets/ts/features/chat/conversationinputs/optimisticInputUserMessage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isObject } from '@core/typeGuards.ts';
import type { ChatContentSegment } from '@features/chat/ChatTypes.ts';
import { buildUserMessageContent } from '@features/chat/messageBuilding.ts';
import { CONVERSATION_INPUT_MESSAGE_ID_FIELD } from '@features/chat/message/messageDomIds.ts';
import { insertMessageByTimestamp } from '@features/chat/message/messageTimestampOrdering.ts';
import type { ChatStorageMessageRecord, Conversation } from '@features/chat/storage/storageModels.ts';

const isServerEpoch = (value: number | undefined): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0 && value < Number.MAX_SAFE_INTEGER;

const resolveOptimisticInputOrderingAnchor = (conversation: Conversation): number => {
    if (!isServerEpoch(conversation.createdAt)) {
        throw new Error('Optimistic conversation input requires a server conversation timestamp.');
    }
    let anchor = conversation.createdAt;
    for (const message of conversation.messages) {
        const timestamp = isObject(message) ? message['timestamp'] : undefined;
        if (isServerEpoch(timestamp) && timestamp > anchor) {
            anchor = timestamp;
        }
    }
    return anchor;
};

const mountOptimisticInputUserMessage = (inputArguments: { conversation: Conversation; inputId: string; acceptedAtMs: number; orderingAnchorTimestamp: number; text: string | null; attachmentContent: readonly ChatContentSegment[] }): void => {
    const normalizedInputId = inputArguments.inputId.trim();
    if (!normalizedInputId) {
        return;
    }
    const messages = inputArguments.conversation.messages;
    if (messages.some((message) => isObject(message) && message[CONVERSATION_INPUT_MESSAGE_ID_FIELD] === normalizedInputId)) {
        return;
    }
    const text = typeof inputArguments.text === 'string' ? inputArguments.text : '';
    if (!text.trim() && inputArguments.attachmentContent.length === 0) {
        return;
    }
    const content = buildUserMessageContent(text, inputArguments.attachmentContent);
    if (content.length === 0) {
        return;
    }
    if (!isServerEpoch(inputArguments.acceptedAtMs) || !isServerEpoch(inputArguments.orderingAnchorTimestamp)) {
        throw new Error('Optimistic conversation input requires valid server ordering timestamps.');
    }
    const timestamp = Math.max(inputArguments.orderingAnchorTimestamp + 1, inputArguments.acceptedAtMs);
    const record: ChatStorageMessageRecord = { role: 'user', content, timestamp };
    record[CONVERSATION_INPUT_MESSAGE_ID_FIELD] = normalizedInputId;
    insertMessageByTimestamp(messages, record, timestamp);
};

export { mountOptimisticInputUserMessage, resolveOptimisticInputOrderingAnchor };
