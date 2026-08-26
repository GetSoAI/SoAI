/* SoAI - Canonical chat message render presentation resolution [frontend/assets/ts/features/chat/message/messageRenderPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isEpochMsValue } from '@core/time/epochMs.ts';
import { isArray } from '@core/typeGuards.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import { isChatMessage } from '@features/chat/message/chatMessageGuards.ts';
import { resolveMessageDomId } from '@features/chat/message/messageDomIds.ts';
import { resolveNormalizedMessageRole } from '@features/chat/message/messageRole.ts';
import { isEmptyAssistantPlaceholderMessage } from '@features/chat/message/placeholderAssistantMessage.ts';
import { resolveActiveStreamingAssistantSelection, type ActiveComparisonRun, type TerminalRenderPendingPredicate } from '@features/chat/message/activeStreamingAssistantMessage.ts';
import type { ChatTurnAdmissionStreamIdentity } from '@features/chat/chatstreamservice/types.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type ChatMessageRenderPresentation = {
    normalizedRole: string;
    isPendingDeletion: boolean;
    isActiveStreamingAssistant: boolean;
    assistantTriggerUserTimestamp: number | null;
    canResendUserMessage: boolean;
};

type MessagePendingDeletionPredicate = (messageDomId: string) => boolean;

const resolveConversationMessageRenderPresentations = (
    conversation: ConversationContract | null,
    inputArguments: {
        activeStreamingAssistantDomIds: ReadonlySet<string>;
        isMessagePendingDeletion: MessagePendingDeletionPredicate;
    }
): readonly ChatMessageRenderPresentation[] => {
    if (conversation === null || !isArray(conversation.messages)) {
        return [];
    }
    const messages = conversation.messages;
    const presentations = new Array<ChatMessageRenderPresentation>(messages.length);
    let latestUserTimestamp: number | null = null;
    for (let messageIndex = 0; messageIndex < messages.length; messageIndex += 1) {
        const message = messages[messageIndex];
        if (!message) {
            continue;
        }
        const normalizedRole = resolveNormalizedMessageRole(message, 'user');
        const messageDomId = resolveMessageDomId(message, messageIndex);
        let assistantTriggerUserTimestamp: number | null = null;
        if (message.role === 'user') {
            latestUserTimestamp = isEpochMsValue(message.timestamp) ? message.timestamp : null;
        } else if (normalizedRole === 'assistant') {
            assistantTriggerUserTimestamp = latestUserTimestamp;
        }
        presentations[messageIndex] = {
            normalizedRole,
            isPendingDeletion: inputArguments.isMessagePendingDeletion(messageDomId),
            isActiveStreamingAssistant: normalizedRole === 'assistant' && inputArguments.activeStreamingAssistantDomIds.has(messageDomId),
            assistantTriggerUserTimestamp,
            canResendUserMessage: false
        };
    }

    let hasAssistantMessageAfter = conversation.history?.hasNewer === true;
    for (let messageIndex = messages.length - 1; messageIndex >= 0; messageIndex -= 1) {
        const message = messages[messageIndex];
        const presentation = presentations[messageIndex];
        if (!message || !presentation) {
            continue;
        }
        if (presentation.normalizedRole === 'user') {
            presentation.canResendUserMessage = !hasAssistantMessageAfter;
            continue;
        }
        if (presentation.normalizedRole !== 'assistant' || !isChatMessage(message) || isEmptyAssistantPlaceholderMessage(message)) {
            continue;
        }
        if (!presentation.isPendingDeletion) {
            hasAssistantMessageAfter = true;
        }
    }
    return presentations;
};

const resolveMessageRenderPresentation = (
    conversation: ConversationContract | null,
    message: ChatMessage,
    messageIndex: number,
    inputArguments: {
        activeStreamingAssistantDomIds: ReadonlySet<string>;
        isMessagePendingDeletion: MessagePendingDeletionPredicate;
    }
): ChatMessageRenderPresentation => {
    if (conversation === null || conversation.messages[messageIndex] !== message) {
        throw new Error('Chat message render presentation requires canonical conversation membership');
    }
    const normalizedRole = resolveNormalizedMessageRole(message, 'user');
    const messageDomId = resolveMessageDomId(message, messageIndex);
    let assistantTriggerUserTimestamp: number | null = null;
    if (message.role !== 'user' && normalizedRole === 'assistant') {
        for (let index = messageIndex - 1; index >= 0; index -= 1) {
            const candidate = conversation.messages[index];
            if (candidate?.role === 'user') {
                assistantTriggerUserTimestamp = isEpochMsValue(candidate.timestamp) ? candidate.timestamp : null;
                break;
            }
        }
    }
    let canResendUserMessage = false;
    if (normalizedRole === 'user' && conversation.history?.hasNewer !== true) {
        canResendUserMessage = true;
        for (let index = messageIndex + 1; index < conversation.messages.length; index += 1) {
            const candidate = conversation.messages[index];
            if (!candidate || resolveNormalizedMessageRole(candidate, 'user') !== 'assistant' || !isChatMessage(candidate) || isEmptyAssistantPlaceholderMessage(candidate)) {
                continue;
            }
            const candidateDomId = resolveMessageDomId(candidate, index);
            if (!inputArguments.isMessagePendingDeletion(candidateDomId)) {
                canResendUserMessage = false;
                break;
            }
        }
    }
    return {
        normalizedRole,
        isPendingDeletion: inputArguments.isMessagePendingDeletion(messageDomId),
        isActiveStreamingAssistant: normalizedRole === 'assistant' && inputArguments.activeStreamingAssistantDomIds.has(messageDomId),
        assistantTriggerUserTimestamp,
        canResendUserMessage
    };
};

const resolveLiveMessageRenderPresentation = (
    conversation: ConversationContract,
    message: ChatMessage,
    messageIndex: number,
    inputArguments: {
        isConversationStreaming: boolean;
        activeComparisonRun: ActiveComparisonRun | null;
        activeStreamIdentity: ChatTurnAdmissionStreamIdentity | null;
        isTerminalRenderPending: TerminalRenderPendingPredicate;
        isMessagePendingDeletion: MessagePendingDeletionPredicate;
    }
): ChatMessageRenderPresentation => {
    const activeStreamingSelection = resolveActiveStreamingAssistantSelection(conversation, {
        isConversationStreaming: inputArguments.isConversationStreaming,
        activeComparisonRun: inputArguments.activeComparisonRun,
        activeStreamIdentity: inputArguments.activeStreamIdentity,
        isTerminalRenderPending: inputArguments.isTerminalRenderPending
    });
    return resolveMessageRenderPresentation(conversation, message, messageIndex, {
        activeStreamingAssistantDomIds: activeStreamingSelection.domIds,
        isMessagePendingDeletion: inputArguments.isMessagePendingDeletion
    });
};

const requireCanonicalMessageIndex = (conversation: ConversationContract, message: ChatMessage): number => {
    const messageIndex = conversation.messages.indexOf(message);
    if (messageIndex < 0) {
        throw new Error('Chat message render requires canonical conversation membership');
    }
    return messageIndex;
};

type LiveMessageRenderPresentationResolverOptions = {
    getCurrentConversation: () => ConversationContract | null;
    isConversationStreaming: (conversationId: string) => boolean;
    getActiveComparisonRun: (conversationId: string) => ActiveComparisonRun | null;
    getActiveStreamIdentity: (conversationId: string) => ChatTurnAdmissionStreamIdentity | null;
    isTerminalRenderPending: TerminalRenderPendingPredicate;
    isMessagePendingDeletion: (conversation: ConversationContract | null, messageDomId: string) => boolean;
};

class LiveMessageRenderPresentationResolver {
    readonly #options: LiveMessageRenderPresentationResolverOptions;

    constructor(options: LiveMessageRenderPresentationResolverOptions) {
        this.#options = options;
    }

    resolve(conversation: ConversationContract, message: ChatMessage, messageIndex: number): ChatMessageRenderPresentation {
        const conversationId = normalizeConversationId(conversation.id);
        return resolveLiveMessageRenderPresentation(conversation, message, messageIndex, {
            isConversationStreaming: conversationId !== null && this.#options.isConversationStreaming(conversationId),
            activeComparisonRun: conversationId === null ? null : this.#options.getActiveComparisonRun(conversationId),
            activeStreamIdentity: conversationId === null ? null : this.#options.getActiveStreamIdentity(conversationId),
            isTerminalRenderPending: this.#options.isTerminalRenderPending,
            isMessagePendingDeletion: (messageDomId) => this.#options.isMessagePendingDeletion(conversation, messageDomId)
        });
    }

    resolveCurrent(message: ChatMessage): ChatMessageRenderPresentation {
        const conversation = this.#options.getCurrentConversation();
        if (conversation === null) {
            throw new Error('Chat message text render requires a current conversation');
        }
        return this.resolve(conversation, message, requireCanonicalMessageIndex(conversation, message));
    }
}

export { LiveMessageRenderPresentationResolver, requireCanonicalMessageIndex, resolveConversationMessageRenderPresentations, resolveLiveMessageRenderPresentation, resolveMessageRenderPresentation };
export type { ChatMessageRenderPresentation, MessagePendingDeletionPredicate };
