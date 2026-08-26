/* SoAI - Streaming message DOM identity resolution for chat page renderer [frontend/assets/ts/pages/chat/controllers/page/renderer/streamingMessageDomIdentityManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray } from '@core/typeGuards.ts';
import { isChatMessageDomOwnedByLiveContainer, normalizeConversationId, resolveMessageDomId, type ChatMessage, type ChatStreamingControllerContext, type ConversationMessage } from '@features/chat/public.ts';

type StreamingMessageDomIdentity = {
    messageDomId: string;
    messageIndex: number;
    messagesReference: ConversationMessage[];
};

type StreamingElementCache = NonNullable<ChatStreamingControllerContext['cachedStreamingElements']>;

const resolveStreamingMessageDomIdentity = (context: ChatStreamingControllerContext, message: ChatMessage, conversationId: string): StreamingMessageDomIdentity => {
    const trimmedConversationId = normalizeConversationId(conversationId);
    if (!trimmedConversationId) {
        throw new Error('Active conversation is not available for message id resolution');
    }
    const conversation = context.dependencies.conversations.get(trimmedConversationId);
    if (!conversation || !isArray(conversation.messages)) {
        throw new Error('Active conversation is not available for message id resolution');
    }
    const messageIndex = conversation.messages.indexOf(message);
    if (messageIndex < 0) {
        throw new Error('Streaming message not found in active conversation');
    }
    return {
        messageDomId: resolveMessageDomId(message, messageIndex),
        messageIndex,
        messagesReference: conversation.messages
    };
};

const cachedStreamingElementsMatchIdentity = (context: ChatStreamingControllerContext, message: ChatMessage, conversationId: string, messagesArea: HTMLElement): StreamingElementCache | null => {
    const cached = context.cachedStreamingElements;
    if (!cached || cached.conversationId !== conversationId || cached.message !== message || cached.messagesArea !== messagesArea || cached.messageIndex === null || cached.messagesReference === null || !cached.messageDomId.trim()) {
        return null;
    }
    const conversation = context.dependencies.conversations.get(conversationId);
    if (!conversation || !isArray(conversation.messages) || conversation.messages !== cached.messagesReference) {
        return null;
    }
    if (cached.messagesReference[cached.messageIndex] !== message) {
        return null;
    }
    if (resolveMessageDomId(message, cached.messageIndex) !== cached.messageDomId) {
        return null;
    }
    if (
        !cached.messageRoot ||
        !cached.messageText ||
        !isChatMessageDomOwnedByLiveContainer({
            liveContainer: messagesArea,
            messageRoot: cached.messageRoot,
            messageDomId: cached.messageDomId,
            messageText: cached.messageText
        })
    ) {
        return null;
    }
    return cached;
};

const bindStreamingElementCacheIdentity = (cache: StreamingElementCache, message: ChatMessage, identity: StreamingMessageDomIdentity): void => {
    cache.message = message;
    cache.messageIndex = identity.messageIndex;
    cache.messagesReference = identity.messagesReference;
};

export { bindStreamingElementCacheIdentity, cachedStreamingElementsMatchIdentity, resolveStreamingMessageDomIdentity };
export type { StreamingMessageDomIdentity };
