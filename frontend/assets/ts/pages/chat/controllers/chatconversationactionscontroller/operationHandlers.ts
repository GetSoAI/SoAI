/* SoAI - Chat page operation handlers [frontend/assets/ts/pages/chat/controllers/chatconversationactionscontroller/operationHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { beginLoadingButtonWithClear } from '@core/ui/loadingbuttons/service.ts';
import { deleteConversations, handleRemoteConversationDeleted, type ConversationDeleteManyOperationOptions } from '@pages/chat/controllers/chatconversationactionscontroller/conversationDeletionController.ts';
import { applyConversationArchiveOperation, applyConversationColorUpdateOperation, applyConversationFavoriteToggleOperation, applyConversationSettingsAuthorityRefresh, collapseSidebarIfNarrowViewport, isArchiveLimitError, type ConversationDeleteOperationOptions } from '@pages/chat/controllers/chatconversationactionscontroller/operations.ts';
import { CONVERSATION_SETTINGS_AUTHORITY_REFRESH_OPERATION_ID, NAVIGATION_OPERATION_ID, createOperationDependencies, enqueueOperation } from '@pages/chat/controllers/chatconversationactionscontroller/conversationOperationExecutionController.ts';
import type { ChatConversationActionsControllerRuntime } from '@pages/chat/controllers/chatconversationactionscontroller/types.ts';

const deleteConversation = async (runtime: ChatConversationActionsControllerRuntime, conversationId: string, options: ConversationDeleteOperationOptions = {}): Promise<void> => {
    await deleteConversations(runtime, [conversationId], options);
};

const deleteManyConversations = async (runtime: ChatConversationActionsControllerRuntime, conversationIds: readonly string[], options: ConversationDeleteManyOperationOptions = {}): Promise<readonly string[]> => {
    const result = await deleteConversations(runtime, conversationIds, options);
    return result.deletedConversationIds;
};

const deleteConversationById = (runtime: ChatConversationActionsControllerRuntime, conversationId: string): void => {
    enqueueOperation(runtime, NAVIGATION_OPERATION_ID, {
        scope: 'chat:deleteConversation',
        task: async () => {
            await deleteConversation(runtime, conversationId);
        },
        logMessage: 'Conversation delete failed',
        errorMessage: i18n.t('chat.conversation.deleteFailed')
    });
};

const handleDeletedConversationEvent = async (runtime: ChatConversationActionsControllerRuntime, conversationId: string): Promise<void> => {
    await handleRemoteConversationDeleted(runtime, conversationId);
};

const handleConversationSettingsAuthorityChangedEvent = (runtime: ChatConversationActionsControllerRuntime, conversationId: string): void => {
    if (runtime.state.getCurrentConversationId() !== conversationId) {
        return;
    }
    enqueueOperation(runtime, CONVERSATION_SETTINGS_AUTHORITY_REFRESH_OPERATION_ID, {
        scope: 'chat:refreshConversationSettingsAuthority',
        task: async () => {
            await applyConversationSettingsAuthorityRefresh(createOperationDependencies(runtime), conversationId);
        },
        logMessage: 'Conversation settings authority refresh failed',
        errorMessage: i18n.t('chat.errors.syncFailed')
    });
};

const updateConversationColorById = (runtime: ChatConversationActionsControllerRuntime, conversationId: string, color: string | null): void => {
    if (!conversationId) {
        return;
    }
    enqueueOperation(runtime, `chat:conversation:${conversationId}`, {
        scope: 'chat:updateConversationColor',
        task: async () => {
            if (!runtime.state.hasConversation(conversationId)) {
                return;
            }
            await applyConversationColorUpdateOperation(createOperationDependencies(runtime), conversationId, color);
        },
        logMessage: 'Conversation color update failed',
        errorMessage: i18n.t('chat.conversation.colorUpdateFailed')
    });
};

const toggleConversationFavoriteById = (runtime: ChatConversationActionsControllerRuntime, conversationId: string, actionElement: HTMLElement | null = null): void => {
    if (!conversationId) {
        return;
    }
    const button = actionElement instanceof HTMLButtonElement ? actionElement : null;
    const clearLoading = button === null ? null : beginLoadingButtonWithClear(button);
    enqueueOperation(runtime, `chat:conversation:${conversationId}`, {
        scope: 'chat:toggleConversationFavorite',
        task: async () => {
            try {
                if (!runtime.state.hasConversation(conversationId)) {
                    return;
                }
                await applyConversationFavoriteToggleOperation(createOperationDependencies(runtime), conversationId);
            } finally {
                clearLoading?.();
            }
        },
        logMessage: 'Conversation favorite toggle failed',
        errorMessage: i18n.t('chat.conversation.favoriteUpdateFailed')
    });
};

const archiveConversationById = (runtime: ChatConversationActionsControllerRuntime, conversationId: string): void => {
    if (!conversationId) {
        return;
    }
    enqueueOperation(runtime, `chat:conversation:${conversationId}`, {
        scope: 'chat:archiveConversation',
        task: async () => {
            if (!runtime.state.hasConversation(conversationId)) {
                return;
            }
            try {
                await applyConversationArchiveOperation(createOperationDependencies(runtime), conversationId);
            } catch (error) {
                const runtimeError = ensureError(error);
                if (isArchiveLimitError(runtimeError)) {
                    runtime.host.workflow.feedback.show(i18n.t('chat.archive.errors.limitReached'), 'error');
                    return;
                }
                throw runtimeError;
            }
        },
        logMessage: 'Conversation archive failed',
        errorMessage: i18n.t('chat.archive.errors.archiveFailed')
    });
};

const collapseSidebarIfNarrowViewportForRuntime = (runtime: ChatConversationActionsControllerRuntime): void => {
    collapseSidebarIfNarrowViewport(createOperationDependencies(runtime));
};

export { archiveConversationById, collapseSidebarIfNarrowViewportForRuntime, deleteConversation, deleteConversationById, deleteManyConversations, handleConversationSettingsAuthorityChangedEvent, handleDeletedConversationEvent, toggleConversationFavoriteById, updateConversationColorById };
