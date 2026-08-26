/* SoAI - Chat RAG ingestion and knowledge attachment session ownership [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/ChatRagAttachmentSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireChatRagIngestionService } from '@core/chat/ragIngestionServiceAccess.ts';
import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import { ChangeNotificationSource } from '@core/primitives/changeNotificationSource.ts';
import { KnowledgeTerminalNotificationRegistry, type RagIngestionStatus } from '@features/chat/public.ts';
import { refreshComposerState, resolveCurrentConversationSelection } from '@pages/chat/controllers/chatmessagesendingcontroller/effects.ts';
import { KnowledgeAttachmentDraftCache, refreshKnowledgeAttachmentDraftCache } from '@pages/chat/controllers/chatmessagesendingcontroller/knowledgeAttachmentDraftCacheManager.ts';
import { startRagIngestionForMessageSending } from '@pages/chat/controllers/chatmessagesendingcontroller/ragIngestionStartController.ts';
import type { MessageSendingHost, StartRagIngestionArguments } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

class ChatRagAttachmentSession {
    readonly #host: MessageSendingHost;
    readonly #knowledgeDrafts = new KnowledgeAttachmentDraftCache();
    readonly #statusChanges = new ChangeNotificationSource();
    readonly #terminalNotifications = new KnowledgeTerminalNotificationRegistry();
    readonly #handleKnowledgeChanged = (summary: KnowledgeAttachmentSummary): void => {
        if (this.#disposed) return;
        const conversationId = this.#applyKnowledgeSummary(summary);
        this.#renderPreviewIfCurrent(conversationId);
    };
    #unsubscribe: (() => void) | null;
    #unsubscribeKnowledgeChanged: (() => void) | null;
    #disposed = false;

    constructor(host: MessageSendingHost) {
        this.#host = host;
        this.#unsubscribe = requireChatRagIngestionService().subscribe(() => this.#handleStatusChange());
        this.#unsubscribeKnowledgeChanged = host.platform.subscribeKnowledgeAttachmentChanged(this.#handleKnowledgeChanged);
    }

    currentStatus(): RagIngestionStatus | null {
        this.#requireActive();
        const selection = resolveCurrentConversationSelection(this.#host);
        return selection ? requireChatRagIngestionService().getStatusForConversation(selection.conversationId) : null;
    }

    statusForConversation(conversationId: string): RagIngestionStatus | null {
        this.#requireActive();
        return requireChatRagIngestionService().getStatusForConversation(conversationId);
    }

    currentKnowledgeDrafts(): KnowledgeAttachmentSummary[] {
        this.#requireActive();
        const selection = resolveCurrentConversationSelection(this.#host);
        return selection ? this.#knowledgeDrafts.get(selection.conversationId) : [];
    }

    refreshKnowledgeDrafts(): void {
        this.#requireActive();
        const selection = resolveCurrentConversationSelection(this.#host);
        if (!selection) return;
        refreshKnowledgeAttachmentDraftCache({
            cache: this.#knowledgeDrafts,
            host: this.#host,
            conversationId: selection.conversationId,
            onUpdated: () => {
                if (!this.#disposed) this.#renderPreviewIfCurrent(selection.conversationId);
            }
        });
    }

    handleKnowledgeChanged(summary: KnowledgeAttachmentSummary): void {
        this.#handleKnowledgeChanged(summary);
    }

    subscribeStatus(handler: () => void): () => void {
        this.#requireActive();
        return this.#statusChanges.subscribe(handler);
    }

    async cancelCurrent(): Promise<void> {
        this.#requireActive();
        const selection = resolveCurrentConversationSelection(this.#host);
        if (selection) await this.cancel(selection.conversationId);
    }

    async cancel(conversationId: string): Promise<void> {
        this.#requireActive();
        await requireChatRagIngestionService().cancel(conversationId);
    }

    async start(inputArguments: StartRagIngestionArguments): Promise<void> {
        this.#requireActive();
        await startRagIngestionForMessageSending(this.#host, inputArguments);
    }

    clearKnowledgeDraftCache(conversationId: string): void {
        this.#knowledgeDrafts.clearConversation(conversationId);
    }

    clearKnowledgeDraftsAndRender(conversationId: string): void {
        this.clearKnowledgeDraftCache(conversationId);
        this.#renderPreviewIfCurrent(conversationId);
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#statusChanges.clear();
        this.#unsubscribe?.();
        this.#unsubscribe = null;
        this.#unsubscribeKnowledgeChanged?.();
        this.#unsubscribeKnowledgeChanged = null;
        this.#knowledgeDrafts.clear();
    }

    #handleStatusChange(): void {
        if (this.#disposed) return;
        const selection = resolveCurrentConversationSelection(this.#host);
        if (selection !== null) {
            const summary = requireChatRagIngestionService().getStatusForConversation(selection.conversationId)?.knowledgeAttachment ?? null;
            if (summary !== null) this.#applyKnowledgeSummary(summary);
        }
        this.refreshKnowledgeDrafts();
        this.#host.presentation.renderAttachedFilesPreview();
        refreshComposerState(this.#host);
        this.#statusChanges.notify();
    }

    #applyKnowledgeSummary(summary: KnowledgeAttachmentSummary): string {
        const application = this.#knowledgeDrafts.applyChangedSummary(summary);
        const notification = application.notificationSummary === null ? null : this.#terminalNotifications.take(application.notificationSummary);
        if (notification !== null) this.#host.platform.feedback.show(notification.message, notification.type);
        const selection = resolveCurrentConversationSelection(this.#host);
        if (selection?.conversationId === application.conversationId) this.#host.services.getAttachmentManager().markKnowledgeAttachmentChanged();
        return application.conversationId;
    }

    #renderPreviewIfCurrent(conversationId: string): void {
        const selection = resolveCurrentConversationSelection(this.#host);
        if (selection?.conversationId !== conversationId) return;
        this.#host.presentation.renderAttachedFilesPreview();
        refreshComposerState(this.#host);
    }

    #requireActive(): void {
        if (this.#disposed) throw new Error('Chat RAG attachment session has been disposed');
    }
}

export { ChatRagAttachmentSession };
