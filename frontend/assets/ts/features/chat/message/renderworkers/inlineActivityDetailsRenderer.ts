/* SoAI - Chat feature inline activity details renderer [frontend/assets/ts/features/chat/message/renderworkers/inlineActivityDetailsRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { createAbortError } from '@core/errors/abort.ts';
import { deepClone } from '@core/primitives/clone.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { buildInlineActivityDetailsRequestKey, resolveInlineActivityDetailsSignatureFromMessage, type InlineActivityDetailsCancelRequest, type InlineActivityDetailsRenderRequest, type InlineActivityDetailsSignatureCheckRequest } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { inlineActivityDetailsIdentitiesMatch, readInlineActivityDetailsSignature, resolveInlineActivityDetailsIdentity } from '@features/chat/message/inlineActivityDetailsLifecycle.ts';
import { clearInlineActivityDetailsPendingState } from '@features/chat/message/inlineActivityDetailsPendingState.ts';
import { resolveMessageDomIdFromElement } from '@features/chat/message/messageDomIds.ts';
import { resolveAssistantMessageRevisionNumberFromMessage } from '@features/chat/message/messageSegmentsResolution.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import type { ChatMessageRenderWorkerClient } from '@features/chat/message/renderworkers/chatMessageRenderWorkerClient.ts';
import { commitInlineActivityDetailsRenderFailure, commitInlineActivityDetailsRenderSuccess } from '@features/chat/message/renderworkers/inlineActivityDetailsDomCommit.ts';
import { hydrateInlineToolDetailsMessage } from '@features/chat/message/renderworkers/inlineActivityDetailsToolHydration.ts';
import { isWorkerRenderContextCurrent } from '@features/chat/message/renderworkers/renderContextGuards.ts';
import type { ChatActivityDurationDisplayMode } from '@features/chat/message/messageview/activityDurationDisplay.ts';

interface ChatMessageInlineActivityDetailsRendererDependencies {
    client: ChatMessageRenderWorkerClient;
    isRichTextEnabled: () => boolean;
    isCodeRecognitionEnabled: () => boolean;
    isThinkingFeatureEnabled: () => boolean;
    isShowActivitiesEnabled: () => boolean;
    getActivityDurationDisplayMode: () => ChatActivityDurationDisplayMode;
    isConversationExecuting: (conversationId: string) => boolean;
    getWorkerRenderEpoch: () => number;
    getCurrentConversationId: () => string | null;
    getCurrentConversation: () => ConversationContract | null;
    resolveMessageForDomId: (conversation: ConversationContract, messageDomId: string) => ChatMessage | null;
    handleError: (error: Error, context: string) => void;
    postRenderEffects: (container: Element | null) => void;
    retryPendingRender: (container: Element | null) => void;
}

interface PendingInlineDetailsRender {
    controller: AbortController;
    signature: string;
    item: HTMLElement;
}

class ChatMessageInlineActivityDetailsRenderer {
    readonly #dependencies: ChatMessageInlineActivityDetailsRendererDependencies;
    readonly #abortByRequestKey: Map<string, PendingInlineDetailsRender>;

    constructor(inputArguments: { dependencies: ChatMessageInlineActivityDetailsRendererDependencies }) {
        this.#dependencies = inputArguments.dependencies;
        this.#abortByRequestKey = new Map();
    }

    dispose(): void {
        for (const pending of this.#abortByRequestKey.values()) {
            pending.controller.abort();
            clearInlineActivityDetailsPendingState(pending.item);
        }
        this.#abortByRequestKey.clear();
    }

    reset(): void {
        this.dispose();
    }

    #clearAbortController(requestKey: string, controller: AbortController): void {
        const pending = this.#abortByRequestKey.get(requestKey) ?? null;
        if (pending === null || pending.controller !== controller) {
            return;
        }
        this.#abortByRequestKey.delete(requestKey);
    }

    #isCurrentRequest(requestKey: string, controller: AbortController): boolean {
        const pending = this.#abortByRequestKey.get(requestKey) ?? null;
        return pending !== null && pending.controller === controller;
    }

    #hasCurrentDetailsSignature(inputArguments: InlineActivityDetailsSignatureCheckRequest, nowMs: number): boolean {
        const activitySignature = readInlineActivityDetailsSignature(inputArguments.item);
        if (activitySignature !== inputArguments.signature) {
            return false;
        }
        return (
            resolveInlineActivityDetailsSignatureFromMessage({
                message: inputArguments.message,
                expectedType: inputArguments.expectedType,
                callId: inputArguments.callId,
                timelineSequenceIndex: inputArguments.timelineSequenceIndex,
                nowMs
            }) === inputArguments.signature
        );
    }

    #resolveCurrentOwnedMessage(inputArguments: { requestKey: string; controller: AbortController; item: HTMLElement; identity: InlineActivityDetailsRenderRequest['identity']; conversationId: string; messageDomId: string; expectedType: InlineActivityDetailsRenderRequest['expectedType']; callId: string; signature: string; nowMs: number }): ChatMessage | null {
        if (!this.#isCurrentRequest(inputArguments.requestKey, inputArguments.controller) || inputArguments.controller.signal.aborted || !inputArguments.item.isConnected) {
            return null;
        }
        if (this.#dependencies.getCurrentConversationId() !== inputArguments.conversationId) {
            return null;
        }
        const currentIdentity = resolveInlineActivityDetailsIdentity(inputArguments.item, inputArguments.conversationId);
        if (currentIdentity === null || !inlineActivityDetailsIdentitiesMatch(currentIdentity, inputArguments.identity)) {
            return null;
        }
        const conversation = this.#dependencies.getCurrentConversation();
        if (conversation === null || conversation.id !== inputArguments.conversationId) {
            return null;
        }
        const message = this.#dependencies.resolveMessageForDomId(conversation, inputArguments.messageDomId);
        if (message === null) {
            return null;
        }
        return this.#hasCurrentDetailsSignature(
            {
                item: inputArguments.item,
                message,
                expectedType: inputArguments.expectedType,
                callId: inputArguments.callId,
                timelineSequenceIndex: inputArguments.identity.timelineSequenceIndex,
                signature: inputArguments.signature
            },
            inputArguments.nowMs
        )
            ? message
            : null;
    }

    #retryPendingRenderOnNextPostRender(requestKey: string, controller: AbortController, item: HTMLElement): void {
        this.#clearAbortController(requestKey, controller);
        if (item.isConnected) {
            this.#dependencies.retryPendingRender(item);
        }
    }

    #renderSettingsAreCurrent(settings: { isRichTextEnabled: boolean; codeRecognitionEnabled: boolean; isThinkingFeatureEnabled: boolean; isShowActivitiesEnabled: boolean; activityDurationDisplayMode: ChatActivityDurationDisplayMode }): boolean {
        return this.#dependencies.isRichTextEnabled() === settings.isRichTextEnabled && this.#dependencies.isCodeRecognitionEnabled() === settings.codeRecognitionEnabled && this.#dependencies.isThinkingFeatureEnabled() === settings.isThinkingFeatureEnabled && this.#dependencies.isShowActivitiesEnabled() === settings.isShowActivitiesEnabled && this.#dependencies.getActivityDurationDisplayMode() === settings.activityDurationDisplayMode;
    }

    renderInlineActivityDetailsAsync(inputArguments: InlineActivityDetailsRenderRequest): void {
        const callId = inputArguments.callId.trim();
        if (!callId) {
            clearInlineActivityDetailsPendingState(inputArguments.item);
            return;
        }
        const signature = inputArguments.signature.trim();
        if (!signature) {
            throw new Error('Inline activity details render requires a signature');
        }

        const conversationId = this.#dependencies.getCurrentConversationId();
        if (!conversationId) {
            clearInlineActivityDetailsPendingState(inputArguments.item);
            return;
        }
        const messageDomId = resolveMessageDomIdFromElement(inputArguments.item);
        if (!messageDomId) {
            clearInlineActivityDetailsPendingState(inputArguments.item);
            return;
        }
        const identity = {
            ...inputArguments.identity,
            conversationId,
            messageDomId
        };
        const requestKey = buildInlineActivityDetailsRequestKey({
            conversationId,
            messageDomId,
            expectedType: inputArguments.expectedType,
            callId,
            timelineSequenceIndex: identity.timelineSequenceIndex
        });
        const previous = this.#abortByRequestKey.get(requestKey) ?? null;
        if (previous !== null && previous.signature === signature && previous.item === inputArguments.item) {
            return;
        }
        if (previous !== null) {
            previous.controller.abort();
            if (previous.item !== inputArguments.item) {
                clearInlineActivityDetailsPendingState(previous.item);
            }
        }
        const controller = new AbortController();
        this.#abortByRequestKey.set(requestKey, { controller, signature, item: inputArguments.item });

        const epoch = this.#dependencies.getWorkerRenderEpoch();
        const nowMs = serverEpochMs();
        const renderSettings = {
            isRichTextEnabled: this.#dependencies.isRichTextEnabled(),
            codeRecognitionEnabled: this.#dependencies.isCodeRecognitionEnabled(),
            isThinkingFeatureEnabled: this.#dependencies.isThinkingFeatureEnabled(),
            isShowActivitiesEnabled: this.#dependencies.isShowActivitiesEnabled(),
            activityDurationDisplayMode: this.#dependencies.getActivityDurationDisplayMode()
        };
        const messageSnapshot = deepClone(inputArguments.message);
        const messageRevision = resolveAssistantMessageRevisionNumberFromMessage(messageSnapshot);
        const context = { epoch, conversationId, messageDomId, messageRevision, stateSignature: `inline-details:${signature}` };
        const isCurrentContext = (message: ChatMessage): boolean => isWorkerRenderContextCurrent(this.#dependencies, { expected: context, messageDomId, messageRevision: resolveAssistantMessageRevisionNumberFromMessage(message), stateSignature: context.stateSignature, signal: controller.signal }) && this.#renderSettingsAreCurrent(renderSettings);

        void hydrateInlineToolDetailsMessage({
            conversationId,
            message: messageSnapshot,
            expectedType: inputArguments.expectedType,
            callId,
            signal: controller.signal
        })
            .then((renderMessage) => {
                const currentMessage = this.#resolveCurrentOwnedMessage({ requestKey, controller, item: inputArguments.item, identity, conversationId, messageDomId, expectedType: inputArguments.expectedType, callId, signature, nowMs });
                if (currentMessage === null || !isCurrentContext(currentMessage)) {
                    throw createAbortError('Inline activity details render was superseded.');
                }
                return this.#dependencies.client.renderInlineDetailsFromMessage({
                    context,
                    ...renderSettings,
                    canonicalPlan: null,
                    isCurrentConversationExecuting: this.#dependencies.isConversationExecuting(conversationId),
                    nowMs,
                    expectedType: inputArguments.expectedType === 'inline_tool_activity' ? 'inline_tool_activity' : 'inline_thinking_activity',
                    callId,
                    timelineSequenceIndex: identity.timelineSequenceIndex,
                    message: renderMessage,
                    signal: controller.signal
                });
            })
            .then((result) => {
                if (controller.signal.aborted) {
                    this.#clearAbortController(requestKey, controller);
                    return;
                }
                if (!this.#isCurrentRequest(requestKey, controller)) {
                    return;
                }
                if (!inputArguments.item.isConnected) {
                    clearInlineActivityDetailsPendingState(inputArguments.item);
                    this.#clearAbortController(requestKey, controller);
                    return;
                }
                const currentMessage = this.#resolveCurrentOwnedMessage({ requestKey, controller, item: inputArguments.item, identity, conversationId, messageDomId, expectedType: inputArguments.expectedType, callId, signature, nowMs });
                if (currentMessage === null) {
                    this.#retryPendingRenderOnNextPostRender(requestKey, controller, inputArguments.item);
                    return;
                }
                if (
                    !isWorkerRenderContextCurrent(this.#dependencies, {
                        expected: result.context,
                        messageDomId,
                        messageRevision: resolveAssistantMessageRevisionNumberFromMessage(currentMessage),
                        stateSignature: context.stateSignature,
                        signal: controller.signal
                    })
                ) {
                    this.#retryPendingRenderOnNextPostRender(requestKey, controller, inputArguments.item);
                    return;
                }
                if (!this.#renderSettingsAreCurrent(renderSettings)) {
                    this.#retryPendingRenderOnNextPostRender(requestKey, controller, inputArguments.item);
                    return;
                }

                commitInlineActivityDetailsRenderSuccess({
                    item: inputArguments.item,
                    signature,
                    html: result.html,
                    postRenderEffects: this.#dependencies.postRenderEffects
                });
                this.#clearAbortController(requestKey, controller);
            })
            .catch((error) => {
                if (controller.signal.aborted) {
                    this.#clearAbortController(requestKey, controller);
                    return;
                }
                if (!this.#isCurrentRequest(requestKey, controller)) {
                    return;
                }
                const currentMessage = this.#resolveCurrentOwnedMessage({ requestKey, controller, item: inputArguments.item, identity, conversationId, messageDomId, expectedType: inputArguments.expectedType, callId, signature, nowMs });
                if (currentMessage === null || !isCurrentContext(currentMessage)) {
                    this.#retryPendingRenderOnNextPostRender(requestKey, controller, inputArguments.item);
                    return;
                }
                const runtimeError = ensureError(error);
                this.#clearAbortController(requestKey, controller);
                this.#dependencies.handleError(runtimeError, 'chat:inlineActivityDetailsRender');
                commitInlineActivityDetailsRenderFailure({ item: inputArguments.item, signature });
            });
    }

    cancelInlineActivityDetailsRender(inputArguments: InlineActivityDetailsCancelRequest): void {
        const conversationId = inputArguments.conversationId.trim();
        const messageDomId = inputArguments.messageDomId.trim();
        const callId = inputArguments.callId.trim();
        if (!conversationId || !messageDomId || !callId) {
            return;
        }
        const requestKey = buildInlineActivityDetailsRequestKey({ conversationId, messageDomId, expectedType: inputArguments.expectedType, callId, timelineSequenceIndex: inputArguments.timelineSequenceIndex });
        const pending = this.#abortByRequestKey.get(requestKey) ?? null;
        if (pending === null) {
            return;
        }
        pending.controller.abort();
        clearInlineActivityDetailsPendingState(pending.item);
        this.#abortByRequestKey.delete(requestKey);
    }
}

export { ChatMessageInlineActivityDetailsRenderer };
export type { ChatMessageInlineActivityDetailsRendererDependencies };
