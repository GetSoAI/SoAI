/* SoAI - Chat conversation toolbar and archived conversation ownership [frontend/assets/ts/pages/chat/controllers/chatpage/conversations/ChatConversationToolbarManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireNonNull } from '@core/assertions.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import type { ChatPageApi } from '@features/chat/public.ts';
import { initializeConversationToolbarForPage, runBatchArchiveForPage, runBatchCloneForPage, runBatchDeleteForPage, type ToolbarWiringHost } from '@pages/chat/controllers/chatpage/construction/toolbarWiring.ts';
import { ArchivedConversationsModalController } from '@pages/chat/controllers/modals/archivedconversations/ArchivedConversationsModalController.ts';
import type { ConversationToolbarController } from '@pages/chat/widgets/conversationtoolbar/toolbarController.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { SelectionState } from '@core/selection/state.ts';

interface ChatConversationToolbarDependencies extends ToolbarWiringHost, ChatUiTaskScopeHost {
    pageContext: { sanitizer: SanitizerApi };
    api: ChatPageApi;
    conversationSelection: SelectionState;
}

class ChatConversationToolbarManager {
    readonly #page: ChatConversationToolbarDependencies;
    #archivedModal: ArchivedConversationsModalController | null = null;
    #controller: ConversationToolbarController | null = null;
    #renderExit: (() => void) | null = null;

    constructor(page: ChatConversationToolbarDependencies) {
        this.#page = page;
    }

    initialize(): void {
        this.#controller?.dispose();
        this.#renderExit?.();
        this.#controller = initializeConversationToolbarForPage(this.#page, this.#page.conversationSelection);
        this.#renderExit = this.#page.conversationView.onRendered(() => this.updateMetrics());
    }

    dispose(): void {
        this.#controller?.dispose();
        this.#controller = null;
        this.#renderExit?.();
        this.#renderExit = null;
        this.#archivedModal?.dispose();
        this.#archivedModal = null;
    }

    updateMetrics(): void {
        this.#controller?.updateMetrics();
    }

    toggleExpanded(): void {
        this.#requireController().toggleExpanded();
    }

    enterSelectMode(): void {
        this.#requireController().enterSelectMode();
    }

    exitSelectMode(): void {
        this.#requireController().exitSelectMode();
    }

    isSelectionActive(): boolean {
        return this.#page.conversationSelection.isActive();
    }

    isConversationSelected(conversationId: string): boolean {
        return this.#page.conversationSelection.has(conversationId);
    }

    toggleConversationSelection(conversationId: string): void {
        this.#requireController().handleConversationClick(conversationId);
    }

    async executeBatchDelete(): Promise<void> {
        await runBatchDeleteForPage(this.#page, this.#requireController());
    }

    async executeBatchClone(): Promise<void> {
        await runBatchCloneForPage(this.#page, this.#requireController());
    }

    async executeBatchArchive(): Promise<void> {
        await runBatchArchiveForPage(this.#page, this.#requireController());
    }

    openArchivedConversations(): void {
        this.#controller?.collapse();
        this.#page.taskScope.run('chat:openArchivedConversations', async () => {
            this.#archivedModal?.dispose();
            this.#archivedModal = new ArchivedConversationsModalController({
                feedback: this.#page.feedback,
                pageContext: this.#page.pageContext,
                api: this.#page.api,
                getCachedIcon: (name, options) => this.#page.presentation.cachedIcon(name, options),
                openConversationEnsuringLoaded: (conversationId) => this.#page.conversationView.requireActions().openConversationEnsuringLoaded(conversationId),
                deleteArchivedConversations: (conversationIds) => this.deleteArchivedConversations(conversationIds),
                refreshSidebarConversationList: () => this.#page.conversationRuntime.requireStorage().refreshConversationList()
            });
            await this.#archivedModal.open();
        });
    }

    async deleteArchivedConversations(conversationIds: readonly string[]): Promise<readonly string[]> {
        const deletedIds = await this.#page.taskScope.runResult('chat:batchOperation', () => this.#deleteArchivedConversationRecords(conversationIds));
        if (deletedIds === undefined) {
            throw new Error('Archived conversation delete task did not produce a result');
        }
        return deletedIds;
    }

    async #deleteArchivedConversationRecords(conversationIds: readonly string[]): Promise<readonly string[]> {
        const mappedIds = conversationIds.filter((conversationId) => this.#page.conversationState.conversations.has(conversationId));
        const unmappedIds = conversationIds.filter((conversationId) => !this.#page.conversationState.conversations.has(conversationId));
        const deletedMappedIds = mappedIds.length === 0 ? [] : await this.#page.conversationView.requireActions().deleteConversations(mappedIds, { confirm: false, notify: false, batchNotify: true });
        const deletedUnmappedIds = unmappedIds.length === 0 ? [] : [...(await this.#page.api.webui.chat.batchDelete(unmappedIds)).deletedIds];
        return [...deletedMappedIds, ...deletedUnmappedIds];
    }

    #requireController(): ConversationToolbarController {
        return requireNonNull(this.#controller, 'ChatPage requires a conversation toolbar controller');
    }
}

export { ChatConversationToolbarManager };
export type { ChatConversationToolbarDependencies };
