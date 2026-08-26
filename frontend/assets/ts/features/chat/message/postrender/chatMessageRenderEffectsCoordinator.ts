/* SoAI - Chat feature message render effects coordinator [frontend/assets/ts/features/chat/message/postrender/chatMessageRenderEffectsCoordinator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonApiClient } from '@core/api/jsonRequestGate.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { SyntaxHighlighter } from '@core/syntaxhighlighter/public.ts';
import { isCanonicalAssistantMessage } from '@features/chat/contentPreviewFeedbackState.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import { ChatInlineMultimediaEnhancer } from '@features/chat/message/enhancers/ChatInlineMultimediaEnhancer.ts';
import { hasChatPostRenderCapability, readChatPostRenderCapabilities } from '@features/chat/message/chatMessagePostRenderCapabilities.ts';
import { ChatPostRenderBatchScheduler, type ChatQueuedPostRenderEntry } from '@features/chat/message/postrender/chatPostRenderBatchScheduler.ts';
import { prepareChatMessageImageLifecycles } from '@features/chat/message/postrender/chatImageLoadLifecycle.ts';
import { runQueuedChatMessagePostRenderEffects } from '@features/chat/message/postrender/chatMessagePostRenderFlush.ts';
import { resolveChatPostRenderTargets } from '@features/chat/message/postrender/chatMessagePostRenderTargets.ts';
import { prepareInlineMultimediaForPostRender, resolveStreamingTextPostRenderCapabilities } from '@features/chat/message/postrender/inlineMultimediaPostRender.ts';
import { StreamingTimelinePostRenderQueue } from '@features/chat/message/postrender/streamingTimelinePostRenderQueue.ts';
import type { ChatPostRenderCommit, ChatPostRenderContainerKey, ChatPostRenderRequestType, ChatQueuedPostRenderMode } from '@features/chat/message/types.ts';
import { disposeThinkingPreviewRuntime, reconcileThinkingPreviewSubtree } from '@features/chat/stream/streamThinkingPreviewRuntime.ts';
import { disposeStreamingSpinnerStatusRuntime, reconcileStreamingSpinnerStatusSubtree } from '@features/chat/stream/streamMessageSpinnerStatusRuntime.ts';
import { syncAssistantBodyCacheFromDom } from '@features/chat/message/postrender/assistantBodyCacheSync.ts';

class ChatMessageRenderEffectsCoordinator {
    readonly #documentRef: Document;
    readonly #syntaxHighlighter: SyntaxHighlighter;
    readonly #apiClient: JsonApiClient;
    readonly #notifyDomChanged: () => void;
    readonly #isInlineMultimediaPreviewsEnabled: () => boolean;
    readonly #getCurrentConversationId: () => string | null;
    readonly #getCurrentConversation: () => ConversationContract | null;
    readonly #resolveMessageForDomId: (conversation: ConversationContract, messageDomId: string) => ChatMessage | null;
    readonly #getPreRenderedAssistantBodyHtml: (message: ChatMessage, workerEpoch: number) => string | null;
    readonly #storePreRenderedAssistantBodyHtml: (message: ChatMessage, html: string, workerEpoch: number) => void;
    readonly #getWorkerRenderEpoch: () => number;
    readonly #shouldCacheSettledAssistantBody: (message: ChatMessage) => boolean;
    readonly #batchScheduler: ChatPostRenderBatchScheduler;
    readonly #streamingTimelineQueue: StreamingTimelinePostRenderQueue;
    #inlineMultimediaEnhancer: ChatInlineMultimediaEnhancer;
    #activeEnhancerKey: ChatPostRenderContainerKey | null;
    #pendingAsyncLayoutWorkCount: number;
    #isDisposed: boolean;

    constructor(inputArguments: { apiClient: JsonApiClient; getDocument: () => Document; syntaxHighlighter: SyntaxHighlighter; notifyDomChanged: () => void; getCurrentConversationId: () => string | null; getCurrentConversation: () => ConversationContract | null; resolveMessageForDomId: (conversation: ConversationContract, messageDomId: string) => ChatMessage | null; getPreRenderedAssistantBodyHtml: (message: ChatMessage, workerEpoch: number) => string | null; storePreRenderedAssistantBodyHtml: (message: ChatMessage, html: string, workerEpoch: number) => void; getWorkerRenderEpoch: () => number; isInlineMultimediaPreviewsEnabled: () => boolean; shouldCacheSettledAssistantBody: (message: ChatMessage) => boolean }) {
        this.#documentRef = inputArguments.getDocument();
        this.#syntaxHighlighter = inputArguments.syntaxHighlighter;
        this.#apiClient = inputArguments.apiClient;
        this.#notifyDomChanged = inputArguments.notifyDomChanged;
        this.#isInlineMultimediaPreviewsEnabled = inputArguments.isInlineMultimediaPreviewsEnabled;
        this.#getCurrentConversationId = inputArguments.getCurrentConversationId;
        this.#getCurrentConversation = inputArguments.getCurrentConversation;
        this.#resolveMessageForDomId = inputArguments.resolveMessageForDomId;
        this.#getPreRenderedAssistantBodyHtml = inputArguments.getPreRenderedAssistantBodyHtml;
        this.#storePreRenderedAssistantBodyHtml = inputArguments.storePreRenderedAssistantBodyHtml;
        this.#getWorkerRenderEpoch = inputArguments.getWorkerRenderEpoch;
        this.#shouldCacheSettledAssistantBody = inputArguments.shouldCacheSettledAssistantBody;
        if (!this.#syntaxHighlighter?.highlight) throw new Error('ChatMessageRenderEffectsCoordinator requires core.syntaxHighlighter');
        if (!this.#isInlineMultimediaPreviewsEnabled) throw new Error('ChatMessageRenderEffectsCoordinator requires isInlineMultimediaPreviewsEnabled');
        this.#isDisposed = false;
        this.#activeEnhancerKey = null;
        this.#pendingAsyncLayoutWorkCount = 0;
        this.#inlineMultimediaEnhancer = this.#createInlineMultimediaEnhancer();
        this.#batchScheduler = new ChatPostRenderBatchScheduler({
            execute: (entry) => this.#executeQueuedEntry(entry),
            reportError: (error, context) => errorHandler.debug('ChatMessageManager', context, error)
        });
        this.#streamingTimelineQueue = new StreamingTimelinePostRenderQueue({
            getCurrentConversationId: () => this.#getCurrentConversationId(),
            getWorkerRenderEpoch: () => this.#getWorkerRenderEpoch(),
            isDisposed: () => this.#isDisposed,
            notifyDomChanged: () => this.#notifyDomChanged()
        });
    }

    dispose(): void {
        this.#isDisposed = true;
        this.#batchScheduler.dispose();
        this.#streamingTimelineQueue.dispose();
        this.#pendingAsyncLayoutWorkCount = 0;
        this.#inlineMultimediaEnhancer.dispose();
        this.#activeEnhancerKey = null;
        disposeThinkingPreviewRuntime(this.#documentRef);
        disposeStreamingSpinnerStatusRuntime(this.#documentRef);
    }

    hasPendingWork(): boolean {
        return !this.#isDisposed && (this.#batchScheduler.hasPendingWork() || this.#streamingTimelineQueue.hasPendingWork() || this.#pendingAsyncLayoutWorkCount > 0);
    }

    postRenderRequest(container: Element | null, type: ChatPostRenderRequestType, onCommitted?: ChatPostRenderCommit): void {
        if (this.#isDisposed || !(container instanceof HTMLElement)) return;
        if (onCommitted !== undefined && type !== 'terminal') throw new Error('Post-render commit callbacks require a terminal request');
        if (type === 'streamingText') {
            this.#runStreamingTextRequest(container);
            return;
        }
        if (type === 'streamingTimeline') {
            this.#streamingTimelineQueue.queue(container);
            return;
        }
        this.#queueResolvedRequest(container, type, onCommitted);
    }

    #queueResolvedRequest(container: HTMLElement, mode: ChatQueuedPostRenderMode, onCommitted?: ChatPostRenderCommit): void {
        const targetResolution = resolveChatPostRenderTargets({
            container,
            conversation: this.#getCurrentConversation(),
            resolveMessageForDomId: (conversation, messageDomId) => this.#resolveMessageForDomId(conversation, messageDomId)
        });
        const targets = targetResolution.targets;
        if (targets.length === 0) return;
        if (onCommitted !== undefined && targets.length !== 1) throw new Error('Post-render commit callbacks require one terminal message root');
        const renderKey = this.#captureRenderKey();
        if (!this.#isRenderKeyCurrent(renderKey)) return;
        this.#activateEnhancer(renderKey);
        reconcileThinkingPreviewSubtree(container);
        reconcileStreamingSpinnerStatusSubtree(container);
        this.#prepareResolvedTargets(targets, targetResolution.assistantMessageByTarget, mode, renderKey, onCommitted);
    }

    #prepareResolvedTargets(targets: readonly HTMLElement[], assistantMessageByTarget: WeakMap<HTMLElement, ChatMessage>, mode: ChatQueuedPostRenderMode, renderKey: ChatPostRenderContainerKey, onCommitted?: ChatPostRenderCommit): void {
        let isBatching = true;
        const notify = (): void => {
            if (!isBatching) this.#notifyDomChanged();
        };
        try {
            for (let index = 0; index < targets.length; index += 1) {
                const target = targets[index];
                if (!target) continue;
                const capabilities = mode === 'full' ? null : readChatPostRenderCapabilities(target);
                const assistantMessage = assistantMessageByTarget.get(target) ?? null;
                this.#syncSettledAssistantBodyCache(target, assistantMessage, renderKey);
                if (mode === 'initialConversation') {
                    const enqueueResult = this.#batchScheduler.enqueue({ target, mode, renderKey, assistantMessage, capabilities, imageLifecyclePrepared: false });
                    if (!enqueueResult.shouldPrepareInitial) continue;
                    if (hasChatPostRenderCapability(capabilities, 'inline-multimedia')) this.#prepareInlineMultimedia(target, assistantMessage);
                    const imageLifecyclePrepared = hasChatPostRenderCapability(capabilities, 'image-lifecycle');
                    if (imageLifecyclePrepared) prepareChatMessageImageLifecycles(target, notify);
                    this.#batchScheduler.completeInitialPreparation(target, enqueueResult.revision, imageLifecyclePrepared);
                    continue;
                }
                if (hasChatPostRenderCapability(capabilities, 'inline-multimedia')) {
                    this.#prepareInlineMultimedia(target, assistantMessage);
                }
                const imageLifecyclePrepared = hasChatPostRenderCapability(capabilities, 'image-lifecycle');
                if (imageLifecyclePrepared) prepareChatMessageImageLifecycles(target, notify);
                this.#batchScheduler.enqueue({
                    target,
                    mode,
                    renderKey,
                    assistantMessage,
                    capabilities,
                    imageLifecyclePrepared,
                    ...(onCommitted !== undefined && index === 0 ? { onCommitted } : {})
                });
            }
        } finally {
            isBatching = false;
            this.#notifyDomChanged();
        }
    }

    #prepareInlineMultimedia(target: HTMLElement, assistantMessage: ChatMessage | null): void {
        prepareInlineMultimediaForPostRender({
            container: target,
            assistantMessage,
            enhancer: this.#inlineMultimediaEnhancer,
            previewsEnabled: this.#isInlineMultimediaPreviewsEnabled()
        });
    }

    #runStreamingTextRequest(container: HTMLElement): void {
        const capabilities = resolveStreamingTextPostRenderCapabilities(container);
        if (capabilities.size === 0) return;
        const renderKey = this.#captureRenderKey();
        if (!this.#isRenderKeyCurrent(renderKey)) return;
        this.#activateEnhancer(renderKey);
        const assistantMessage = this.#resolveCanonicalAssistantMessage(container);
        if (hasChatPostRenderCapability(capabilities, 'inline-multimedia')) this.#prepareInlineMultimedia(container, assistantMessage);
        this.#batchScheduler.enqueue({ target: container, mode: 'full', renderKey, assistantMessage, capabilities, imageLifecyclePrepared: false });
    }

    #executeQueuedEntry(entry: ChatQueuedPostRenderEntry): void {
        if (this.#isDisposed || !entry.target.isConnected || !this.#isRenderKeyCurrent(entry.renderKey) || !this.#batchScheduler.isLatest(entry)) return;
        this.#activateEnhancer(entry.renderKey);
        runQueuedChatMessagePostRenderEffects({
            node: entry.target,
            syntaxHighlighter: this.#syntaxHighlighter,
            inlineMultimediaEnhancer: this.#inlineMultimediaEnhancer,
            renderKey: entry.renderKey,
            assistantMessage: entry.assistantMessage,
            notifyDomChanged: () => this.#notifyDomChanged(),
            inlineMultimediaPreviewsEnabled: this.#isInlineMultimediaPreviewsEnabled(),
            increasePendingAsyncLayoutWork: () => {
                this.#pendingAsyncLayoutWorkCount += 1;
            },
            decreasePendingAsyncLayoutWork: () => {
                this.#pendingAsyncLayoutWorkCount = Math.max(0, this.#pendingAsyncLayoutWorkCount - 1);
            },
            storePreRenderedAssistantBodyHtml: (message, html) => this.#storePreRenderedAssistantBodyHtml(message, html, entry.renderKey.epoch),
            capabilities: entry.capabilities,
            mode: entry.mode,
            imageLifecyclePrepared: entry.imageLifecyclePrepared,
            isExecutionCurrent: () => !this.#isDisposed && entry.target.isConnected && this.#isRenderKeyCurrent(entry.renderKey) && this.#batchScheduler.isLatest(entry)
        });
    }

    #syncSettledAssistantBodyCache(target: HTMLElement, message: ChatMessage | null, renderKey: ChatPostRenderContainerKey): void {
        if (message === null || this.#isInlineMultimediaPreviewsEnabled() || !this.#shouldCacheSettledAssistantBody(message)) return;
        if (this.#getPreRenderedAssistantBodyHtml(message, renderKey.epoch) !== null) return;
        try {
            syncAssistantBodyCacheFromDom({
                container: target,
                assistantMessage: message,
                storePreRenderedAssistantBodyHtml: (candidateMessage, html) => this.#storePreRenderedAssistantBodyHtml(candidateMessage, html, renderKey.epoch)
            });
        } catch (error) {
            errorHandler.debug('ChatMessageManager', 'Assistant body DOM cache synchronization failed', ensureError(error));
        }
    }

    #captureRenderKey(): ChatPostRenderContainerKey {
        return { conversationId: this.#getCurrentConversationId(), epoch: this.#getWorkerRenderEpoch() };
    }

    #isRenderKeyCurrent(renderKey: ChatPostRenderContainerKey): boolean {
        return this.#getCurrentConversationId() === renderKey.conversationId && this.#getWorkerRenderEpoch() === renderKey.epoch;
    }

    #activateEnhancer(renderKey: ChatPostRenderContainerKey): void {
        if (this.#activeEnhancerKey?.conversationId === renderKey.conversationId && this.#activeEnhancerKey.epoch === renderKey.epoch) return;
        this.#inlineMultimediaEnhancer.dispose();
        this.#inlineMultimediaEnhancer = this.#createInlineMultimediaEnhancer();
        this.#activeEnhancerKey = renderKey;
    }

    #createInlineMultimediaEnhancer(): ChatInlineMultimediaEnhancer {
        return new ChatInlineMultimediaEnhancer({
            apiClient: this.#apiClient,
            notifyDomChanged: () => this.#notifyDomChanged()
        });
    }

    #resolveCanonicalAssistantMessage(container: HTMLElement): ChatMessage | null {
        const conversation = this.#getCurrentConversation();
        if (conversation === null) return null;
        const messageRoot = container.closest('.chat-message.assistant');
        if (!(messageRoot instanceof HTMLElement)) return null;
        const messageDomId = (messageRoot.getAttribute('data-id') ?? '').trim();
        if (!messageDomId) return null;
        const message = this.#resolveMessageForDomId(conversation, messageDomId);
        return isCanonicalAssistantMessage(message) ? message : null;
    }
}

export { ChatMessageRenderEffectsCoordinator };
