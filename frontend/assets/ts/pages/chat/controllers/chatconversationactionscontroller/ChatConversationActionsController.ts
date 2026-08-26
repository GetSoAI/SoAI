/* SoAI - Chat conversation action ownership [frontend/assets/ts/pages/chat/controllers/chatconversationactionscontroller/ChatConversationActionsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_PAGE, type SaveController } from '@core/save/public.ts';
import { sanitizeTitle, type Conversation } from '@features/chat/public.ts';
import { archiveConversationById, collapseSidebarIfNarrowViewportForRuntime, deleteConversation, deleteConversationById, deleteManyConversations, handleConversationSettingsAuthorityChangedEvent, handleDeletedConversationEvent, toggleConversationFavoriteById, updateConversationColorById } from '@pages/chat/controllers/chatconversationactionscontroller/operationHandlers.ts';
import { activateConversationById, clearConversationSelection, createConversation, handleNewConversationClick, openConversationEnsuringLoaded, switchConversationById } from '@pages/chat/controllers/chatconversationactionscontroller/conversationSelectionController.ts';
import type { ConversationDeleteManyOperationOptions } from '@pages/chat/controllers/chatconversationactionscontroller/conversationDeletionController.ts';
import type { ConversationDeleteOperationOptions, ConversationOperationOptions } from '@pages/chat/controllers/chatconversationactionscontroller/operations.ts';
import { cancelConversationRenameOnBlur, handleConversationListTitleCancel, handleConversationTitleCancel, startConversationRenameById, startCurrentConversationTitleEdit, updateConversationRenameDraftValue } from '@pages/chat/controllers/chatconversationactionscontroller/renameHandlers.ts';
import { persistConversationRename } from '@pages/chat/controllers/chatconversationactionscontroller/service.ts';
import type { ChatConversationActionsControllerRuntime, ChatConversationSettingsManager, ChatStreamingController, ComposerDraftManager, ConversationActionsHost, ConversationActionsStateAccess, ConversationManager, MessageDeleteManager, StorageManager, UiManager } from '@pages/chat/controllers/chatconversationactionscontroller/types.ts';
import type { ChatConcurrencyController } from '@pages/chat/controllers/page/concurrency/ChatConcurrencyController.ts';
import type { ChatConversationActionsContract } from '@pages/chat/controllers/chatconversationactionscontroller/contracts.ts';

class ChatConversationActionsController implements ChatConversationActionsContract {
    #runtime: ChatConversationActionsControllerRuntime;
    readonly #renameSave: SaveController;

    constructor(options: { host: ConversationActionsHost; state: ConversationActionsStateAccess; conversationManager: ConversationManager; storageManager: StorageManager; uiManager: UiManager; chatStreamingController: ChatStreamingController; conversationSettingsManager: ChatConversationSettingsManager | null; getComposerDraftManager(): ComposerDraftManager | null; getMessageDeleteManager(): MessageDeleteManager | null; concurrencyScope: ChatConcurrencyController }) {
        this.#runtime = {
            host: options.host,
            state: options.state,
            conversationManager: options.conversationManager,
            storageManager: options.storageManager,
            uiManager: options.uiManager,
            chatStreamingController: options.chatStreamingController,
            conversationSettingsManager: options.conversationSettingsManager,
            getComposerDraftManager: () => options.getComposerDraftManager(),
            getMessageDeleteManager: () => options.getMessageDeleteManager(),
            concurrencyScope: options.concurrencyScope
        };
        this.#renameSave = createSaveController({
            headerContextId: 'chat-conversation-rename',
            headerPriority: SAVE_HEADER_PRIORITY_PAGE,
            requestContextLabel: 'Chat conversation rename',
            units: [
                {
                    id: 'chat-conversation-rename',
                    hasChanges: () => this.#hasConversationRenameChanges(),
                    save: async () => {
                        await persistConversationRename(this.#runtime.host, this.#runtime.state, this.#runtime.conversationManager, this.#runtime.storageManager);
                    }
                }
            ]
        });
        this.#renameSave.attach({ resolveSaveButtons: () => this.#resolveRenameSaveButtons(), autoNotifyRoot: null });
    }

    setConversationSettingsManager(manager: ChatConversationSettingsManager | null): void {
        this.#runtime.conversationSettingsManager = manager;
    }

    dispose(): void {
        this.#renameSave.dispose();
    }

    notifySaveChanged(): void {
        this.#renameSave.notifyChanged();
    }

    async activateConversationById(conversationId: string, options: ConversationOperationOptions = {}): Promise<void> {
        await activateConversationById(this.#runtime, conversationId, options);
    }

    async clearConversationSelection(options: ConversationOperationOptions = {}): Promise<void> {
        await clearConversationSelection(this.#runtime, options);
    }

    async createConversation(options: ConversationOperationOptions = {}): Promise<Conversation | null> {
        return createConversation(this.#runtime, options);
    }

    async ensureConversationPersisted(conversation: Conversation): Promise<void> {
        await this.#runtime.conversationManager.ensureConversationPersisted(conversation);
    }

    switchConversationById(conversationId: string): void {
        switchConversationById(this.#runtime, conversationId);
    }

    deleteConversationById(conversationId: string): void {
        deleteConversationById(this.#runtime, conversationId);
    }

    async deleteConversation(conversationId: string, options: ConversationDeleteOperationOptions = {}): Promise<void> {
        await deleteConversation(this.#runtime, conversationId, options);
    }

    async deleteConversations(conversationIds: readonly string[], options: ConversationDeleteManyOperationOptions = {}): Promise<readonly string[]> {
        return await deleteManyConversations(this.#runtime, conversationIds, options);
    }

    handleConversationSettingsAuthorityChangedEvent(conversationId: string): void {
        handleConversationSettingsAuthorityChangedEvent(this.#runtime, conversationId);
    }

    async handleDeletedConversationEvent(conversationId: string): Promise<void> {
        await handleDeletedConversationEvent(this.#runtime, conversationId);
    }

    updateConversationColorById(conversationId: string, color: string | null): void {
        updateConversationColorById(this.#runtime, conversationId, color);
    }

    toggleConversationFavoriteById(conversationId: string, actionElement: HTMLElement | null = null): void {
        toggleConversationFavoriteById(this.#runtime, conversationId, actionElement);
    }

    archiveConversationById(conversationId: string): void {
        archiveConversationById(this.#runtime, conversationId);
    }

    openConversationEnsuringLoaded(conversationId: string): void {
        openConversationEnsuringLoaded(this.#runtime, conversationId);
    }

    handleNewConversationClick(actionElement: HTMLElement | null = null): void {
        handleNewConversationClick(this.#runtime, actionElement);
    }

    collapseSidebarIfNarrowViewport(): void {
        collapseSidebarIfNarrowViewportForRuntime(this.#runtime);
    }

    async startConversationRenameById(conversationId: string): Promise<void> {
        await startConversationRenameById(this.#runtime, conversationId);
    }

    async startCurrentConversationTitleEdit(): Promise<void> {
        await startCurrentConversationTitleEdit(this.#runtime);
    }

    updateConversationRenameDraft(value: string): void {
        updateConversationRenameDraftValue(this.#runtime, value);
    }

    async handleConversationTitleBlur(event: Event): Promise<void> {
        await cancelConversationRenameOnBlur(this.#runtime, event, '.conversation-title-save-btn, .conversation-title-cancel-btn');
    }

    async handleConversationListTitleBlur(event: Event): Promise<void> {
        await cancelConversationRenameOnBlur(this.#runtime, event, '.rename-save-conversation, .rename-cancel-conversation');
    }

    async handleConversationTitleSave(): Promise<void> {
        await this.#renameSave.requestSave();
        this.#runtime.host.view.getConversationTitleInputElement()?.blur();
    }

    async handleConversationListTitleSave(): Promise<void> {
        await this.#renameSave.requestSave();
        this.#runtime.host.view.getConversationListTitleInputElement()?.blur();
    }

    handleConversationTitleCancel(): void {
        handleConversationTitleCancel(this.#runtime);
    }

    handleConversationListTitleCancel(): void {
        handleConversationListTitleCancel(this.#runtime);
    }

    #resolveRenameSaveButtons(): readonly HTMLButtonElement[] {
        const buttons: HTMLButtonElement[] = [];
        const headerInput = this.#runtime.host.view.getConversationTitleInputElement();
        const headerRoot = headerInput ? headerInput.closest('.conversation-title-wrapper') : null;
        const headerSave = headerRoot instanceof HTMLElement ? dom.resolve('.conversation-title-save-btn', headerRoot) : null;
        if (headerSave instanceof HTMLButtonElement) {
            buttons.push(headerSave);
        }
        const listInput = this.#runtime.host.view.getConversationListTitleInputElement();
        const listRoot = listInput ? listInput.closest('.conversation-item') : null;
        const listSave = listRoot instanceof HTMLElement ? dom.resolve('.rename-save-conversation', listRoot) : null;
        if (listSave instanceof HTMLButtonElement) {
            buttons.push(listSave);
        }
        return buttons;
    }

    #hasConversationRenameChanges(): boolean {
        const renameState = this.#runtime.state.getConversationRenameState();
        if (!renameState) {
            return false;
        }
        const normalizedDraft = sanitizeTitle(renameState.draft);
        const normalizedOriginal = sanitizeTitle(renameState.originalTitle);
        return normalizedDraft !== normalizedOriginal;
    }
}

export { ChatConversationActionsController };
export type { ChatConversationSettingsManager, ChatStreamingController, ComposerDraftManager, ConversationActionsHost, ConversationActionsStateAccess, ConversationManager, MessageDeleteManager, StorageManager, UiManager };
