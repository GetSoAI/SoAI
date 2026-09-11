/* SoAI - Chat feature message service [frontend/assets/ts/features/chat/message/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SyntaxHighlighter } from '@core/syntaxhighlighter/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import { resolveMessageContainer } from '@features/chat/message/messageEditing.ts';
import type { ChatMessageRenderModel } from '@features/chat/message/messageRenderModel.ts';
import { createChatMessageActions } from '@features/chat/message/actionControllerFactory.ts';
import type { ChatMessageActions } from '@features/chat/message/actions.ts';
import type { ChatMessageActionData } from '@features/chat/message/actionDeps.ts';
import { ChatMessageDeleteUndoController } from '@features/chat/message/messageDeleteUndoController.ts';
import type { AttachmentOverflowRecord } from '@features/chat/message/attachmentoverflowmodal/records.ts';
import { ChatMessageModalCoordinator } from '@features/chat/message/modalCoordinator.ts';
import type { ResolvedMessageReference } from '@features/chat/message/messageReferenceResolution.ts';
import { ChatMessageState } from '@features/chat/message/state.ts';
import type { ChatMessageManagerDependencies, ChatPostRenderCommit, ChatPostRenderRequestType } from '@features/chat/message/types.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import { ChatMessageView } from '@features/chat/message/view.ts';
import { ChatMessageWorkerRenderingRuntime } from '@features/chat/message/messageWorkerRenderingRuntime.ts';
import { normalizeMessageDomId } from '@features/chat/message/messageDomIds.ts';
import { resolveInlineToolIconHtml } from '@features/chat/message/toolActivityIconHtml.ts';
import { resolveRunningActivityRefreshDelayMs } from '@features/chat/message/activityRefreshDelay.ts';
import type { RunningActivitySummary } from '@features/chat/toolactivity/runningActivitySummary.ts';
import type { MessageRenderOptions, RenderedMessageTextContent } from '@features/chat/message/messageview/types.ts';
import type { InlineActivityDetailsCancelRequest, InlineActivityDetailsRenderRequest } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { LiveMessageRenderPresentationResolver } from '@features/chat/message/messageRenderPresentation.ts';
import { resolveNormalizedMessageRole } from '@features/chat/message/messageRole.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

class ChatMessageManager {
    readonly #dependencies: ChatMessageManagerDependencies;
    readonly #modalCoordinator: ChatMessageModalCoordinator;
    readonly #state: ChatMessageState;
    readonly #deleteUndoController: ChatMessageDeleteUndoController;
    readonly #actions: ChatMessageActions;
    readonly #view: ChatMessageView;
    readonly #workerRenderingRuntime: ChatMessageWorkerRenderingRuntime;
    readonly #renderPresentationResolver: LiveMessageRenderPresentationResolver;

    constructor(chatPage: ChatMessageManagerDependencies, syntaxHighlighter: SyntaxHighlighter) {
        this.#dependencies = chatPage;
        this.#state = new ChatMessageState();
        this.#deleteUndoController = new ChatMessageDeleteUndoController({
            getCurrentConversation: () => this.#dependencies.session.getCurrentConversation(),
            resolveConversationById: (conversationId) => this.#dependencies.session.resolveConversationById(conversationId),
            runWithBoundary: (name, functionValue) => this.#dependencies.interaction.runWithBoundary(name, functionValue),
            resolveMessageReference: (conversation, messageDomId) => this.#state.resolveMessageReference(conversation, messageDomId),
            invalidateChatMarkup: (scope) => this.#dependencies.runtime.invalidateChatMarkup(scope),
            renderCurrentConversation: () => this.#dependencies.runtime.renderCurrentConversation(),
            renderConversationList: () => this.#dependencies.runtime.renderConversationList(),
            saveAndSync: (conversation) => this.#dependencies.runtime.saveAndSync(conversation),
            deleteMessageByCursor: (conversation, inputArguments) => this.#dependencies.runtime.deleteMessageByCursor(conversation, inputArguments),
            runConversationExecutionIfIdle: (conversationId, task) => this.#dependencies.runtime.runConversationExecutionIfIdle(conversationId, task),
            showNotification: (message, type) => this.#dependencies.interaction.showNotification(message, type),
            notifyConversationContentCommitted: () => this.#dependencies.interaction.notifyConversationContentCommitted(),
            getDeleteFailedText: () => i18n.t('chat.message.deleteFailed')
        });
        this.#renderPresentationResolver = new LiveMessageRenderPresentationResolver({
            getCurrentConversation: () => this.#dependencies.session.getCurrentConversation(),
            isConversationStreaming: (conversationId) => this.#dependencies.runtime.isChatStreamingConversation(conversationId),
            getActiveComparisonRun: (conversationId) => this.#dependencies.session.getActiveComparisonRun(conversationId),
            getActiveStreamIdentity: (conversationId) => this.#dependencies.session.getActiveStreamIdentity(conversationId),
            isTerminalRenderPending: (conversationId, message) => this.#dependencies.session.isTerminalRenderPending(conversationId, message),
            isMessagePendingDeletion: (conversation, messageDomId) => this.#deleteUndoController.isPendingForConversation(conversation, messageDomId)
        });
        this.#modalCoordinator = new ChatMessageModalCoordinator({
            knowledgeAttachmentsApi: this.#dependencies.boundary.knowledgeAttachmentsApi,
            soaiPathsApi: this.#dependencies.boundary.soaiPathsApi,
            escapeHtml: (value: string): string => this.#dependencies.presentation.sanitizer.html(value),
            runWithBoundary: (name, functionValue) => this.#dependencies.interaction.runWithBoundary(name, functionValue),
            hasClipboardSupport: () => this.#dependencies.interaction.hasClipboardSupport(),
            copyToClipboard: (text, options) => this.#dependencies.interaction.copyToClipboard(text, options),
            showNotification: (message, type) => this.#dependencies.interaction.showNotification(message, type),
            getAttachmentDraftRevision: () => this.#dependencies.rendering.getAttachmentDraftRevision(),
            onKnowledgeAttachmentChanged: (summary) => this.#dependencies.interaction.onKnowledgeAttachmentChanged(summary)
        });

        this.#view = new ChatMessageView({
            sanitizer: this.#dependencies.presentation.sanitizer,
            getCanonicalPlan: () => this.#dependencies.session.getCanonicalPlan(),
            isConversationExecuting: (conversationId) => this.#dependencies.session.isConversationExecuting(conversationId),
            presentationPreferences: {
                isThinkingFeatureEnabled: () => this.#dependencies.presentation.isThinkingFeatureEnabled(),
                isRichTextEnabled: () => this.#dependencies.presentation.isRichTextEnabled(),
                isCodeRecognitionEnabled: () => this.#dependencies.presentation.isCodeRecognitionEnabled(),
                isInlineMultimediaPreviewsEnabled: () => this.#dependencies.presentation.isInlineMultimediaPreviewsEnabled(),
                isShowActivitiesEnabled: () => this.#dependencies.presentation.isShowActivitiesEnabled(),
                getActivityDurationDisplayMode: () => this.#dependencies.presentation.getActivityDurationDisplayMode()
            },
            getIcon: (name: IconName, options?: IconOptions): TrustedHtml => this.#dependencies.presentation.getCachedIcon(name, options),
            getToolIconHtml: (toolName: string): string | null => resolveInlineToolIconHtml(this.#dependencies.presentation.chatToolIconService, toolName),
            getCurrentConversationId: () => normalizeConversationId(this.#dependencies.session.getCurrentConversation()?.id),
            getCurrentRunningActivitySnapshot: () => this.#dependencies.session.getCurrentRunningActivitySnapshot(),
            getMessageSenderLabel: (source, defaultRole) => this.#dependencies.presentation.getMessageSenderLabel(source, defaultRole),
            resolveMessageContentSegments: (message) => this.#state.resolveMessageContentSegments(message),
            resolveRunningActivitySummaryForMarkup: (message, nowMs) => this.#state.resolveRunningActivitySummaryForMarkup(message, nowMs),
            getPreRenderedAssistantBodyHtml: (message) => this.#state.getPreRenderedAssistantBodyHtml(message, this.#dependencies.rendering.getWorkerRenderEpoch()),
            getLoadingActivityCollapsedState: (message) => this.#state.getLoadingActivityCollapsedState(message),
            toggleLoadingActivityCollapsedState: (message, defaultCollapsed) => this.#state.toggleLoadingActivityCollapsedState(message, defaultCollapsed),
            handleError: (error, context, options) => this.#dependencies.interaction.handleError(error, context, options),
            avatars: {
                getAssistantAvatarUrl: () => this.#dependencies.presentation.getAssistantAvatarUrl(),
                getUserAvatarUrl: () => this.#dependencies.presentation.getUserAvatarUrl()
            }
        });

        const domChangeTarget = new EventTarget();
        this.#workerRenderingRuntime = new ChatMessageWorkerRenderingRuntime({
            dependencies: {
                boundary: this.#dependencies.boundary,
                interaction: this.#dependencies.interaction,
                presentation: this.#dependencies.presentation,
                rendering: this.#dependencies.rendering,
                session: this.#dependencies.session,
                state: this.#state,
                view: this.#view,
                syntaxHighlighter,
                notifyDomChanged: () => domChangeTarget.dispatchEvent(new Event('change'))
            }
        });

        this.#actions = createChatMessageActions({
            dependencies: this.#dependencies,
            domChangeTarget,
            deleteUndoController: this.#deleteUndoController,
            modalCoordinator: this.#modalCoordinator,
            host: {
                assistantRenderPort: this,
                getIcon: (name, options) => this.#dependencies.presentation.getCachedIcon(name, options),
                resolveMessageReference: (conversation, messageId) => this.#state.resolveMessageReference(conversation, messageId),
                resolveMessageContentSegments: (message) => this.#state.resolveMessageContentSegments(message),
                renderMessageTextContent: (message) => this.#view.renderMessageTextContent(message, this.#renderPresentationResolver.resolveCurrent(message)),
                resolveMessageContainer: (messageId) => this.#resolveMessageContainer(messageId),
                isShowActivitiesEnabled: () => this.#dependencies.presentation.isShowActivitiesEnabled(),
                toggleLoadingActivityCollapsedState: (message, defaultCollapsed) => this.#state.toggleLoadingActivityCollapsedState(message, defaultCollapsed),
                invalidateMessageCache: (message) => this.#state.invalidateMessageCache(message),
                postRender: (container) => this.#workerRenderingRuntime.postRenderRequest(container, 'full')
            }
        });
    }

    refreshRenderWorkerResources(): void {
        this.#workerRenderingRuntime.refreshResources();
    }

    invalidatePresentationRendering(): void {
        this.#workerRenderingRuntime.invalidatePresentationRendering();
    }

    getMessageTextFragments(message: ChatMessage): string[] {
        return this.#state.getMessageTextFragments(message);
    }

    clearCache(): void {
        this.#state.clearCache();
    }

    dispose(): void {
        this.#workerRenderingRuntime.dispose();
        this.clearCache();
        this.#actions.dispose();
        this.#deleteUndoController.dispose();
        this.#modalCoordinator.dispose();
    }

    invalidateMessageCache(message: ChatMessage | null | undefined): void {
        this.#state.invalidateMessageCache(message);
    }

    invalidateMessageProjectionCache(message: ChatMessage | null | undefined): void {
        this.#state.invalidateMessageProjectionCache(message);
    }

    showAttachmentOverflowRecords(conversationId: string, records: readonly AttachmentOverflowRecord[]): void {
        this.#modalCoordinator.showAttachmentOverflowRecords(conversationId, records);
    }

    isShowActivitiesEnabled(): boolean {
        return this.#dependencies.presentation.isShowActivitiesEnabled();
    }

    getLoadingActivityCollapsedState(message: ChatMessage): boolean | null {
        return this.#state.getLoadingActivityCollapsedState(message);
    }

    toggleLoadingActivityCollapsedState(message: ChatMessage, defaultCollapsed: boolean): boolean {
        return this.#state.toggleLoadingActivityCollapsedState(message, defaultCollapsed);
    }

    resolveMessageContentSegments(message: ChatMessage | null | undefined): MessageSegment[] {
        return this.#state.resolveMessageContentSegments(message);
    }

    resolveRunningActivitySummary(message: ChatMessage, nowMs: number): RunningActivitySummary {
        return this.#state.resolveRunningActivitySummary(message, nowMs);
    }

    resolveRunningActivityRefreshDelayMs(message: ChatMessage, nowMs: number): number | null {
        const summary = this.resolveRunningActivitySummary(message, nowMs);
        const summaryDelayMs = summary.nextVisibleAtMs === null ? null : Math.max(0, summary.nextVisibleAtMs - nowMs);
        return resolveRunningActivityRefreshDelayMs(message, () => this.resolveMessageContentSegments(message), nowMs, summaryDelayMs, this.#dependencies.presentation.getActivityDurationDisplayMode());
    }

    resolveMessageReference(conversation: ConversationContract | null, messageId: string): ResolvedMessageReference {
        return this.#state.resolveMessageReference(conversation, messageId);
    }

    getIcon(iconName: IconName, options?: IconOptions): TrustedHtml {
        return this.#dependencies.presentation.getCachedIcon(iconName, options);
    }

    escapeHtml(value: string): string {
        return this.#dependencies.presentation.sanitizer.html(value);
    }

    escapeAttribute(value: string): string {
        return this.#dependencies.presentation.sanitizer.attribute(value);
    }

    renderMessageTextContent(message: ChatMessage, segments: MessageSegment[] | null = null): string {
        return this.#view.renderMessageTextContent(message, this.#renderPresentationResolver.resolveCurrent(message), segments);
    }

    renderActiveStreamMessageTextContent(message: ChatMessage): RenderedMessageTextContent {
        const normalizedRole = resolveNormalizedMessageRole(message, 'user');
        return this.#view.renderActiveStreamMessageTextContent(message, {
            normalizedRole,
            isPendingDeletion: false,
            isActiveStreamingAssistant: normalizedRole === 'assistant',
            assistantTriggerUserTimestamp: null,
            canResendUserMessage: false
        });
    }

    isMessagePendingDeletion(conversation: ConversationContract | null, messageDomId: string): boolean {
        return this.#deleteUndoController.isPendingForConversation(conversation, messageDomId);
    }

    resolveMessageRenderPresentation(conversation: ConversationContract, message: ChatMessage, messageIndex: number): ChatMessageRenderModel['presentation'] {
        return this.#renderPresentationResolver.resolve(conversation, message, messageIndex);
    }

    renderSegments(segments: MessageSegment[], options: MessageRenderOptions = {}): string {
        return this.#view.renderSegments(segments, options);
    }

    renderMarkdownContent(content: string, options: { sortableTables?: boolean } = {}): string {
        return this.#view.renderMarkdownContent(content, options);
    }

    renderStreamingMarkdownContent(content: string): string {
        return this.#view.renderStreamingMarkdownContent(content);
    }

    getWorkerRenderEpoch(): number {
        return this.#dependencies.rendering.getWorkerRenderEpoch();
    }

    renderInlineActivityDetailsAsync(inputArguments: InlineActivityDetailsRenderRequest): void {
        this.#workerRenderingRuntime.renderInlineActivityDetailsAsync(inputArguments);
    }

    cancelInlineActivityDetailsRender(inputArguments: InlineActivityDetailsCancelRequest): void {
        this.#workerRenderingRuntime.cancelInlineActivityDetailsRender(inputArguments);
    }

    renderMessage(model: ChatMessageRenderModel): TrustedHtml {
        return this.#view.renderMessage(model, (modelId) => this.#dependencies.presentation.getModelTypeLabel(modelId));
    }

    async handleMessageAction(messageId: string, action: string | null | undefined, data?: ChatMessageActionData): Promise<void> {
        return this.#actions.handleMessageAction(messageId, action, data);
    }

    handleDeleteUndoHoverChange(messageDomId: string, hovering: boolean): void {
        const normalizedMessageDomId = normalizeMessageDomId(messageDomId);
        if (!normalizedMessageDomId) {
            return;
        }
        const conversation = this.#dependencies.session.getCurrentConversation();
        if (!conversation) {
            return;
        }
        if (!this.#deleteUndoController.isPendingForConversation(conversation, normalizedMessageDomId)) {
            return;
        }
        if (hovering) {
            this.#deleteUndoController.pauseDeleteCountdown(conversation, normalizedMessageDomId);
            return;
        }
        this.#deleteUndoController.resumeDeleteCountdown(conversation, normalizedMessageDomId);
    }

    async commitPendingDeletesForConversation(conversation: ConversationContract): Promise<void> {
        await this.#deleteUndoController.commitAllPendingDeletes(conversation);
    }

    resumePausedDeletesForConversation(conversation: ConversationContract): void {
        this.#deleteUndoController.resumePausedDeletesForConversation(conversation);
    }

    postRender(container: Element | null): void {
        this.#workerRenderingRuntime.postRenderRequest(container, 'full');
    }

    postRenderRequest(container: Element | null, type: ChatPostRenderRequestType, onCommitted?: ChatPostRenderCommit): void {
        this.#workerRenderingRuntime.postRenderRequest(container, type, onCommitted);
    }

    async preRenderConversationAssistantBodies(conversation: ConversationContract, options: { signal: AbortSignal | null }): Promise<void> {
        await this.#workerRenderingRuntime.preRenderConversationAssistantBodies(conversation, { signal: options.signal });
    }

    hasPendingPostRenderWork(): boolean {
        return this.#workerRenderingRuntime.hasPendingPostRenderWork();
    }

    #resolveMessageContainer(messageId: string): HTMLElement | null {
        const normalizedMessageId = normalizeMessageDomId(messageId);
        if (!normalizedMessageId) {
            return null;
        }
        const document = this.#dependencies.presentation.dom.getDocument();
        return resolveMessageContainer(document, normalizedMessageId);
    }
}

export { ChatMessageManager };
