/* SoAI - Assistant body pre-rendering powered by workers [frontend/assets/ts/features/chat/message/renderworkers/assistantBodyWorkerRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentCanonicalPlan } from '@core/chat/agentTypes.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import { runBoundedRequests } from '@features/chat/messagerenderworker/boundedRequestScheduler.ts';
import { resolveAssistantMessageRevisionNumberFromMessage } from '@features/chat/message/messageSegmentsResolution.ts';
import { resolveChatMessageRenderSignature } from '@features/chat/message/messageRenderSignature.ts';
import { resolveMessageDomId } from '@features/chat/message/messageDomIds.ts';
import { isAssistantMessageRole, resolveNormalizedMessageRole } from '@features/chat/message/messageRole.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import type { ChatMessageRenderWorkerClient } from '@features/chat/message/renderworkers/chatMessageRenderWorkerClient.ts';
import { isWorkerRenderContextCurrent } from '@features/chat/message/renderworkers/renderContextGuards.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';
import type { ChatActivityDurationDisplayMode } from '@features/chat/message/messageview/activityDurationDisplay.ts';

interface ChatMessageAssistantBodyWorkerDependencies {
    client: Pick<ChatMessageRenderWorkerClient, 'getWorkerCount' | 'renderAssistantBodyFromMessage'>;
    getWorkerRenderEpoch: () => number;
    getCurrentConversationId: () => string | null;
    getCurrentConversation: () => ConversationContract | null;
    isRichTextEnabled: () => boolean;
    isCodeRecognitionEnabled: () => boolean;
    isThinkingFeatureEnabled: () => boolean;
    isShowActivitiesEnabled: () => boolean;
    getActivityDurationDisplayMode: () => ChatActivityDurationDisplayMode;
    isInlineMultimediaPreviewsEnabled: () => boolean;
    shouldCacheSettledAssistantBody: (message: ChatMessage) => boolean;
    getPreRenderedAssistantBodyHtml: (message: ChatMessage, workerEpoch: number) => string | null;
    storePreRenderedAssistantBodyHtml: (message: ChatMessage, html: string, workerEpoch: number) => void;
    isConversationExecuting: (conversationId: string) => boolean;
    getCanonicalPlan: () => AgentCanonicalPlan | null;
    handleError: (error: Error, context: string) => void;
}

const isChatMessageWithKnownRole = (value: ConversationContract['messages'][number]): value is ChatMessage => {
    if (!isObject(value) || isArray(value)) {
        return false;
    }
    const roleValue = value.role;
    if (!isString(roleValue)) {
        return false;
    }
    const normalized = resolveNormalizedMessageRole(value);
    return normalized === 'assistant' || normalized === 'user' || normalized === 'system' || normalized === 'tool';
};

class ChatMessageAssistantBodyWorkerRenderer {
    readonly #dependencies: ChatMessageAssistantBodyWorkerDependencies;

    constructor(inputArguments: { dependencies: ChatMessageAssistantBodyWorkerDependencies }) {
        this.#dependencies = inputArguments.dependencies;
    }

    async preRenderConversationAssistantBodies(inputArguments: { conversation: ConversationContract; signal: AbortSignal | null }): Promise<void> {
        const conversationId = normalizeConversationId(inputArguments.conversation.id);
        if (!conversationId) {
            throw new Error('Conversation id is required for assistant pre-render');
        }
        if (this.#dependencies.isInlineMultimediaPreviewsEnabled()) {
            return;
        }
        const epoch = this.#dependencies.getWorkerRenderEpoch();
        const messages = isArray(inputArguments.conversation.messages) ? inputArguments.conversation.messages : [];
        const factories: Array<() => Promise<void>> = [];

        for (let index = 0; index < messages.length; index += 1) {
            const message = messages[index];
            if (!message || !isChatMessageWithKnownRole(message) || !isAssistantMessageRole(message)) {
                continue;
            }
            if (!this.#dependencies.shouldCacheSettledAssistantBody(message)) {
                continue;
            }
            const messageDomId = resolveMessageDomId(message, index);
            const messageRevision = resolveAssistantMessageRevisionNumberFromMessage(message);
            const stateSignature = resolveChatMessageRenderSignature(message, null);
            factories.push(async () => {
                if (!this.#isRequestCurrent({ conversation: inputArguments.conversation, conversationId, epoch, index, message, messageDomId, messageRevision, signal: inputArguments.signal, stateSignature })) return;
                if (this.#dependencies.getPreRenderedAssistantBodyHtml(message, epoch) !== null) return;
                const result = await this.#dependencies.client.renderAssistantBodyFromMessage({
                    context: { epoch, conversationId, messageDomId, messageRevision, stateSignature },
                    isRichTextEnabled: this.#dependencies.isRichTextEnabled(),
                    codeRecognitionEnabled: this.#dependencies.isCodeRecognitionEnabled(),
                    isThinkingFeatureEnabled: this.#dependencies.isThinkingFeatureEnabled(),
                    isShowActivitiesEnabled: this.#dependencies.isShowActivitiesEnabled(),
                    activityDurationDisplayMode: this.#dependencies.getActivityDurationDisplayMode(),
                    isCurrentConversationExecuting: this.#dependencies.isConversationExecuting(conversationId),
                    canonicalPlan: this.#dependencies.getCanonicalPlan(),
                    suppressAssistantActivityWidgets: false,
                    nowMs: serverEpochMs(),
                    message,
                    signal: inputArguments.signal
                });
                if (!this.#isRequestCurrent({ conversation: inputArguments.conversation, conversationId, epoch, index, message, messageDomId, messageRevision, signal: inputArguments.signal, stateSignature })) return;
                if (!isWorkerRenderContextCurrent(this.#dependencies, { expected: result.context, messageDomId, messageRevision, stateSignature, signal: inputArguments.signal })) return;
                if (this.#dependencies.getPreRenderedAssistantBodyHtml(message, epoch) !== null) return;
                this.#dependencies.storePreRenderedAssistantBodyHtml(message, result.html, result.context.epoch);
            });
        }

        if (factories.length === 0) {
            return;
        }
        const maxInFlight = this.#dependencies.client.getWorkerCount();
        try {
            await runBoundedRequests({ factories, maxInFlight, signal: inputArguments.signal });
        } catch (error) {
            if (inputArguments.signal?.aborted) {
                return;
            }
            const runtimeError = ensureError(error);
            this.#dependencies.handleError(runtimeError, 'chat:assistantBodyPreRender');
        }
    }

    #isRequestCurrent(inputArguments: { conversation: ConversationContract; conversationId: string; epoch: number; index: number; message: ChatMessage; messageDomId: string; messageRevision: number; signal: AbortSignal | null; stateSignature: string }): boolean {
        if (inputArguments.signal?.aborted || this.#dependencies.getWorkerRenderEpoch() !== inputArguments.epoch) return false;
        if (this.#dependencies.getCurrentConversationId() !== inputArguments.conversationId || this.#dependencies.getCurrentConversation() !== inputArguments.conversation) return false;
        if (inputArguments.conversation.messages[inputArguments.index] !== inputArguments.message) return false;
        if (resolveMessageDomId(inputArguments.message, inputArguments.index) !== inputArguments.messageDomId) return false;
        if (resolveAssistantMessageRevisionNumberFromMessage(inputArguments.message) !== inputArguments.messageRevision) return false;
        return resolveChatMessageRenderSignature(inputArguments.message, null) === inputArguments.stateSignature;
    }
}

export { ChatMessageAssistantBodyWorkerRenderer };
export type { ChatMessageAssistantBodyWorkerDependencies };
