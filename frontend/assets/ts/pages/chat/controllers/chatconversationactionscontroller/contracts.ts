/* SoAI - Chat conversation action controller contracts [frontend/assets/ts/pages/chat/controllers/chatconversationactionscontroller/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ComposerDraftTransferMode, Conversation } from '@features/chat/public.ts';

interface ConversationOperationOptions {
    refreshUi?: boolean;
    syncRoute?: boolean;
    transferMode?: ComposerDraftTransferMode;
}

interface ConversationDeleteOperationOptions {
    confirm?: boolean;
    notify?: boolean;
}

interface ConversationDeleteManyOperationOptions extends ConversationDeleteOperationOptions {
    batchNotify?: boolean;
}

interface ConversationDeleteFallbackSnapshot {
    activeConversationId: string | null;
    visibleConversationIds: readonly string[];
    preferredUnarchivedConversationIds: readonly string[];
    allUnarchivedConversationIds: readonly string[];
}

interface ChatConversationSettingsManagerContract {
    handleConversationSwitch?: (conversationId: string | null) => void;
    handleConversationDeleted?: (conversationId: string) => void;
}

interface ChatConversationActionsContract {
    setConversationSettingsManager(manager: ChatConversationSettingsManagerContract | null): void;
    dispose(): void;
    notifySaveChanged(): void;
    activateConversationById(conversationId: string, options?: ConversationOperationOptions): Promise<void>;
    clearConversationSelection(options?: ConversationOperationOptions): Promise<void>;
    createConversation(options?: ConversationOperationOptions): Promise<Conversation | null>;
    ensureConversationPersisted(conversation: Conversation): Promise<void>;
    switchConversationById(conversationId: string): void;
    deleteConversationById(conversationId: string): void;
    deleteConversation(conversationId: string, options?: ConversationDeleteOperationOptions): Promise<void>;
    deleteConversations(conversationIds: readonly string[], options?: ConversationDeleteManyOperationOptions): Promise<readonly string[]>;
    handleConversationSettingsAuthorityChangedEvent(conversationId: string): void;
    handleDeletedConversationEvent(conversationId: string): Promise<void>;
    updateConversationColorById(conversationId: string, color: string | null): void;
    toggleConversationFavoriteById(conversationId: string, actionElement?: HTMLElement | null): void;
    archiveConversationById(conversationId: string): void;
    openConversationEnsuringLoaded(conversationId: string): void;
    handleNewConversationClick(actionElement?: HTMLElement | null): void;
    collapseSidebarIfNarrowViewport(): void;
    startConversationRenameById(conversationId: string): Promise<void>;
    startCurrentConversationTitleEdit(): Promise<void>;
    updateConversationRenameDraft(value: string): void;
    handleConversationTitleBlur(event: Event): Promise<void>;
    handleConversationListTitleBlur(event: Event): Promise<void>;
    handleConversationTitleSave(): Promise<void>;
    handleConversationListTitleSave(): Promise<void>;
    handleConversationTitleCancel(): void;
    handleConversationListTitleCancel(): void;
}

export type { ChatConversationActionsContract, ChatConversationSettingsManagerContract, ConversationDeleteFallbackSnapshot, ConversationDeleteManyOperationOptions, ConversationDeleteOperationOptions, ConversationOperationOptions };
