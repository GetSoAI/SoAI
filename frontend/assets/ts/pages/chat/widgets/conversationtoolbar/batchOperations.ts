/* SoAI - Chat page batch operations [frontend/assets/ts/pages/chat/widgets/conversationtoolbar/batchOperations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { APIError } from '@core/apiError.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { Conversation } from '@features/chat/public.ts';

interface BatchDeleteDependencies {
    conversations: ReadonlyMap<string, Conversation>;
    deleteConversations(conversationIds: readonly string[]): Promise<readonly string[]>;
    showNotification(message: string, type: NotificationType): void;
    refreshConversationsUI(): Promise<void>;
    invalidateChatMarkup(scope: 'current' | 'list' | 'both'): void;
    saveChatState(force?: boolean): void;
    exitSelectMode(): void;
}

interface BatchCloneDependencies {
    conversations: Map<string, Conversation>;
    createConversationId(): string;
    cloneConversation(sourceConversationId: string, targetConversationId: string): Promise<Conversation>;
    showNotification(message: string, type: NotificationType): void;
    refreshConversationsUI(): Promise<void>;
    invalidateChatMarkup(scope: 'current' | 'list' | 'both'): void;
    saveChatState(force?: boolean): void;
    exitSelectMode(): void;
}

interface BatchArchiveDependencies {
    conversations: ReadonlyMap<string, Conversation>;
    setArchived(conversationId: string, isArchived: boolean): Promise<void>;
    showNotification(message: string, type: NotificationType): void;
    refreshConversationsUI(): Promise<void>;
    invalidateChatMarkup(scope: 'current' | 'list' | 'both'): void;
    saveChatState(force?: boolean): void;
    exitSelectMode(): void;
}

interface BatchOperationFinalizeDependencies {
    refreshConversationsUI(): Promise<void>;
    invalidateChatMarkup(scope: 'current' | 'list' | 'both'): void;
    saveChatState(force?: boolean): void;
    exitSelectMode(): void;
}

const finalizeBatchOperation = async (dependencies: BatchOperationFinalizeDependencies): Promise<void> => {
    dependencies.exitSelectMode();
    dependencies.saveChatState(true);
    dependencies.invalidateChatMarkup('current');
    await dependencies.refreshConversationsUI();
};

const executeBatchDelete = async (dependencies: BatchDeleteDependencies, selectedIds: readonly string[]): Promise<void> => {
    if (selectedIds.length === 0) {
        return;
    }
    const confirmMessage = i18n.t('chat.toolbar.batchDeleteConfirm', { count: selectedIds.length });
    const confirmTitle = i18n.t('chat.toolbar.batchDeleteTitle');
    const confirmed = await requireDialogsService().showConfirmation({
        title: confirmTitle,
        message: confirmMessage,
        confirmText: i18n.t('common.delete'),
        variant: 'danger'
    });
    if (!confirmed) {
        return;
    }
    const deletableIds = selectedIds.filter((conversationId) => dependencies.conversations.has(conversationId));
    let deletedConversationIds: readonly string[] = [];
    let lastError: Error | null = null;
    try {
        deletedConversationIds = await dependencies.deleteConversations(deletableIds);
    } catch (error) {
        lastError = ensureError(error);
    }
    await finalizeBatchOperation(dependencies);
    if (lastError) {
        dependencies.showNotification(i18n.t('chat.toolbar.batchDeleteFailed'), 'error');
        throw lastError;
    }
    if (deletedConversationIds.length > 0) {
        dependencies.showNotification(i18n.t('chat.toolbar.batchDeleteSuccess', { count: deletedConversationIds.length }), 'success');
    }
};

const executeBatchClone = async (dependencies: BatchCloneDependencies, selectedIds: readonly string[]): Promise<void> => {
    if (selectedIds.length === 0) {
        return;
    }
    let clonedCount = 0;
    let lastError: Error | null = null;
    for (const conversationId of selectedIds) {
        const initialSource = dependencies.conversations.get(conversationId);
        if (!initialSource) continue;
        try {
            const cloned = await dependencies.cloneConversation(conversationId, dependencies.createConversationId());
            dependencies.conversations.set(cloned.id, cloned);
            clonedCount += 1;
        } catch (error) {
            lastError = ensureError(error);
        }
    }
    await finalizeBatchOperation(dependencies);
    if (lastError) {
        dependencies.showNotification(i18n.t('chat.toolbar.batchCloneFailed'), 'error');
        throw lastError;
    }
    if (clonedCount > 0) {
        dependencies.showNotification(i18n.t('chat.toolbar.batchCloneSuccess', { count: clonedCount }), 'success');
    }
};

const executeBatchArchive = async (dependencies: BatchArchiveDependencies, selectedIds: readonly string[]): Promise<void> => {
    if (selectedIds.length === 0) {
        return;
    }
    let archivedCount = 0;
    let lastError: Error | null = null;
    for (const conversationId of selectedIds) {
        if (!dependencies.conversations.has(conversationId)) {
            continue;
        }
        try {
            await dependencies.setArchived(conversationId, true);
            archivedCount += 1;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (runtimeError instanceof APIError && runtimeError.code === 'archive_limit_reached') {
                dependencies.showNotification(i18n.t('chat.archive.errors.limitReached'), 'error');
                break;
            }
            lastError = runtimeError;
        }
    }
    await finalizeBatchOperation(dependencies);
    if (lastError) {
        dependencies.showNotification(i18n.t('chat.archive.errors.archiveFailed'), 'error');
        throw lastError;
    }
    if (archivedCount > 0) {
        dependencies.showNotification(i18n.t('chat.toolbar.batchArchiveSuccess', { count: archivedCount }), 'success');
    }
};

export { executeBatchArchive, executeBatchClone, executeBatchDelete };
export type { BatchArchiveDependencies, BatchCloneDependencies, BatchDeleteDependencies };
