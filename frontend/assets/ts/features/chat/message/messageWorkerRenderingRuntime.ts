/* SoAI - Worker rendering runtime and post-render effects for chat messages [frontend/assets/ts/features/chat/message/messageWorkerRenderingRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { SyntaxHighlighter } from '@core/syntaxhighlighter/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { ChatMessageRenderEffectsCoordinator } from '@features/chat/message/postrender/chatMessageRenderEffectsCoordinator.ts';
import type { ChatMessageBoundaryPort, ChatMessageInteractionPort, ChatMessagePresentationPort, ChatMessageRenderingPort, ChatMessageSessionPort, ChatPostRenderCommit, ChatPostRenderRequestType } from '@features/chat/message/types.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import { ChatMessageRenderWorkerClient } from '@features/chat/message/renderworkers/chatMessageRenderWorkerClient.ts';
import { ChatMessageAssistantBodyWorkerRenderer } from '@features/chat/message/renderworkers/assistantBodyWorkerRenderer.ts';
import { ChatMessageInlineActivityDetailsRenderer } from '@features/chat/message/renderworkers/inlineActivityDetailsRenderer.ts';
import { InlineActivityDetailsRefreshScheduler, containerHasRefreshableInlineActivityDetails } from '@features/chat/message/renderworkers/inlineActivityDetailsRefresh.ts';
import type { InlineActivityDetailsCancelRequest, InlineActivityDetailsRenderRequest } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import type { ChatMessageState } from '@features/chat/message/state.ts';
import type { ChatMessageView } from '@features/chat/message/view.ts';

interface ChatMessageWorkerRenderingRuntimeDependencies {
    boundary: Pick<ChatMessageBoundaryPort, 'apiClient'>;
    interaction: Pick<ChatMessageInteractionPort, 'handleError'>;
    presentation: Pick<ChatMessagePresentationPort, 'dom' | 'getActivityDurationDisplayMode' | 'getCachedIcon' | 'isCodeRecognitionEnabled' | 'isInlineMultimediaPreviewsEnabled' | 'isRichTextEnabled' | 'isShowActivitiesEnabled' | 'isThinkingFeatureEnabled'>;
    rendering: Pick<ChatMessageRenderingPort, 'getWorkerRenderEpoch'>;
    session: Pick<ChatMessageSessionPort, 'getCanonicalPlan' | 'getCurrentConversation' | 'isConversationExecuting'>;
    state: Pick<ChatMessageState, 'getPreRenderedAssistantBodyHtml' | 'resetPreRenderedAssistantBodyCache' | 'resolveMessageReference' | 'storePreRenderedAssistantBodyHtml'>;
    view: Pick<ChatMessageView, 'shouldCacheSettledAssistantBody'>;
    syntaxHighlighter: SyntaxHighlighter;
    notifyDomChanged: () => void;
}

class ChatMessageWorkerRenderingRuntime {
    readonly #dependencies: ChatMessageWorkerRenderingRuntimeDependencies;
    readonly #renderEffectsCoordinator: ChatMessageRenderEffectsCoordinator;
    readonly #renderWorkerClient: ChatMessageRenderWorkerClient;
    readonly #assistantBodyWorkerRenderer: ChatMessageAssistantBodyWorkerRenderer;
    readonly #inlineDetailsRenderer: ChatMessageInlineActivityDetailsRenderer;
    readonly #inlineDetailsRefreshScheduler: InlineActivityDetailsRefreshScheduler;

    constructor(inputArguments: { dependencies: ChatMessageWorkerRenderingRuntimeDependencies }) {
        this.#dependencies = inputArguments.dependencies;
        this.#renderEffectsCoordinator = new ChatMessageRenderEffectsCoordinator({
            apiClient: this.#dependencies.boundary.apiClient,
            getDocument: () => this.#dependencies.presentation.dom.getDocument(),
            syntaxHighlighter: this.#dependencies.syntaxHighlighter,
            notifyDomChanged: () => this.#dependencies.notifyDomChanged(),
            getCurrentConversationId: () => this.#dependencies.session.getCurrentConversation()?.id ?? null,
            getCurrentConversation: () => this.#dependencies.session.getCurrentConversation(),
            resolveMessageForDomId: (conversation: ConversationContract, messageDomId: string) => this.#dependencies.state.resolveMessageReference(conversation, messageDomId).message,
            getPreRenderedAssistantBodyHtml: (message: ChatMessage, workerEpoch: number) => this.#dependencies.state.getPreRenderedAssistantBodyHtml(message, workerEpoch),
            storePreRenderedAssistantBodyHtml: (message: ChatMessage, html: string, workerEpoch: number) => this.#dependencies.state.storePreRenderedAssistantBodyHtml(message, html, workerEpoch),
            getWorkerRenderEpoch: () => this.#dependencies.rendering.getWorkerRenderEpoch(),
            shouldCacheSettledAssistantBody: (message: ChatMessage) => this.#dependencies.view.shouldCacheSettledAssistantBody(message),
            isInlineMultimediaPreviewsEnabled: () => this.#dependencies.presentation.isInlineMultimediaPreviewsEnabled()
        });
        this.#renderWorkerClient = new ChatMessageRenderWorkerClient({
            dependencies: {
                getIconHtml: (name: IconName, options?: IconOptions) => this.#dependencies.presentation.getCachedIcon(name, options).html
            }
        });
        this.#assistantBodyWorkerRenderer = new ChatMessageAssistantBodyWorkerRenderer({
            dependencies: {
                client: this.#renderWorkerClient,
                getCanonicalPlan: () => this.#dependencies.session.getCanonicalPlan(),
                getWorkerRenderEpoch: () => this.#dependencies.rendering.getWorkerRenderEpoch(),
                isRichTextEnabled: () => this.#dependencies.presentation.isRichTextEnabled(),
                isCodeRecognitionEnabled: () => this.#dependencies.presentation.isCodeRecognitionEnabled(),
                isThinkingFeatureEnabled: () => this.#dependencies.presentation.isThinkingFeatureEnabled(),
                isShowActivitiesEnabled: () => this.#dependencies.presentation.isShowActivitiesEnabled(),
                getActivityDurationDisplayMode: () => this.#dependencies.presentation.getActivityDurationDisplayMode(),
                isInlineMultimediaPreviewsEnabled: () => this.#dependencies.presentation.isInlineMultimediaPreviewsEnabled(),
                shouldCacheSettledAssistantBody: (message: ChatMessage) => this.#dependencies.view.shouldCacheSettledAssistantBody(message),
                getPreRenderedAssistantBodyHtml: (message: ChatMessage, workerEpoch: number) => this.#dependencies.state.getPreRenderedAssistantBodyHtml(message, workerEpoch),
                getCurrentConversation: () => this.#dependencies.session.getCurrentConversation(),
                storePreRenderedAssistantBodyHtml: (message: ChatMessage, html: string, workerEpoch: number) => this.#dependencies.state.storePreRenderedAssistantBodyHtml(message, html, workerEpoch),
                isConversationExecuting: (conversationId: string) => this.#dependencies.session.isConversationExecuting(conversationId),
                getCurrentConversationId: () => this.#dependencies.session.getCurrentConversation()?.id ?? null,
                handleError: (error: Error, context: string) => this.#handleError(error, context)
            }
        });
        this.#inlineDetailsRenderer = new ChatMessageInlineActivityDetailsRenderer({
            dependencies: {
                client: this.#renderWorkerClient,
                isRichTextEnabled: () => this.#dependencies.presentation.isRichTextEnabled(),
                isCodeRecognitionEnabled: () => this.#dependencies.presentation.isCodeRecognitionEnabled(),
                isThinkingFeatureEnabled: () => this.#dependencies.presentation.isThinkingFeatureEnabled(),
                isShowActivitiesEnabled: () => this.#dependencies.presentation.isShowActivitiesEnabled(),
                getActivityDurationDisplayMode: () => this.#dependencies.presentation.getActivityDurationDisplayMode(),
                isConversationExecuting: (conversationId: string) => this.#dependencies.session.isConversationExecuting(conversationId),
                getWorkerRenderEpoch: () => this.#dependencies.rendering.getWorkerRenderEpoch(),
                getCurrentConversationId: () => this.#dependencies.session.getCurrentConversation()?.id ?? null,
                handleError: (error: Error, context: string) => this.#handleError(error, context),
                postRenderEffects: (container: Element | null) => this.#postRenderRequest(container, 'streamingTimeline'),
                retryPendingRender: (container: Element | null) => this.#postRenderRequest(container, 'full')
            }
        });
        this.#inlineDetailsRefreshScheduler = new InlineActivityDetailsRefreshScheduler({
            getCurrentConversation: () => this.#dependencies.session.getCurrentConversation(),
            resolveMessageReferenceForDomId: (conversation: ConversationContract, messageDomId: string) => this.#dependencies.state.resolveMessageReference(conversation, messageDomId),
            renderInlineActivityDetailsAsync: (inputArguments) => this.#inlineDetailsRenderer.renderInlineActivityDetailsAsync(inputArguments)
        });
    }

    #handleError(error: Error, context: string): void {
        this.#dependencies.interaction.handleError(ensureError(error), context, { notify: false, severity: 'error' });
    }

    dispose(): void {
        this.#inlineDetailsRefreshScheduler.dispose();
        this.#renderEffectsCoordinator.dispose();
        this.#inlineDetailsRenderer.dispose();
        this.#renderWorkerClient.dispose();
    }

    refreshResources(): void {
        this.#renderWorkerClient.refreshResources();
        this.invalidatePresentationRendering();
    }

    invalidatePresentationRendering(): void {
        this.#dependencies.state.resetPreRenderedAssistantBodyCache();
        this.#inlineDetailsRenderer.reset();
        this.#inlineDetailsRefreshScheduler.dispose();
    }

    postRenderRequest(container: Element | null, type: ChatPostRenderRequestType, onCommitted?: ChatPostRenderCommit): void {
        this.#postRenderRequest(container, type, onCommitted);
    }

    #postRenderRequest(container: Element | null, type: ChatPostRenderRequestType, onCommitted?: ChatPostRenderCommit): void {
        this.#renderEffectsCoordinator.postRenderRequest(container, type, onCommitted);
        if (type === 'initialConversation' || type === 'full' || type === 'terminal' || (type === 'streamingTimeline' && containerHasRefreshableInlineActivityDetails(container))) {
            this.#inlineDetailsRefreshScheduler.queue(container);
        }
    }

    hasPendingPostRenderWork(): boolean {
        return this.#renderEffectsCoordinator.hasPendingWork();
    }

    async preRenderConversationAssistantBodies(conversation: ConversationContract, options: { signal: AbortSignal | null }): Promise<void> {
        await this.#assistantBodyWorkerRenderer.preRenderConversationAssistantBodies({ conversation, signal: options.signal });
    }

    renderInlineActivityDetailsAsync(inputArguments: InlineActivityDetailsRenderRequest): void {
        this.#inlineDetailsRenderer.renderInlineActivityDetailsAsync(inputArguments);
    }

    cancelInlineActivityDetailsRender(inputArguments: InlineActivityDetailsCancelRequest): void {
        this.#inlineDetailsRenderer.cancelInlineActivityDetailsRender(inputArguments);
    }
}

export { ChatMessageWorkerRenderingRuntime };
export type { ChatMessageWorkerRenderingRuntimeDependencies };
