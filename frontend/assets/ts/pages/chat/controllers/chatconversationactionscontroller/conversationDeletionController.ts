/* SoAI - Chat conversation deletion recovery operations [frontend/assets/ts/pages/chat/controllers/chatconversationactionscontroller/conversationDeletionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { isProtectedEmptyConversation } from '@features/chat/public.ts';
import { clearLocalConversationDeletes, isLocalConversationDeletePending, markLocalConversationDeletes } from '@pages/chat/controllers/chatconversationactionscontroller/conversationDeletionCoordinatorController.ts';
import { activateConversationById, clearConversationSelection, createConversation } from '@pages/chat/controllers/chatconversationactionscontroller/conversationSelectionController.ts';
import type { ConversationDeleteOperationOptions } from '@pages/chat/controllers/chatconversationactionscontroller/operations.ts';
import { cancelConversationRename } from '@pages/chat/controllers/chatconversationactionscontroller/service.ts';
import type { ChatConversationActionsControllerRuntime } from '@pages/chat/controllers/chatconversationactionscontroller/types.ts';
import type { ConversationDeleteFallbackSnapshot, ConversationDeleteManyOperationOptions } from '@pages/chat/controllers/chatconversationactionscontroller/contracts.ts';
import type { ConversationActivationSnapshot } from '@pages/chat/controllers/page/concurrency/ChatConcurrencyController.ts';

interface ConversationDeleteResult {
    deletedConversationIds: readonly string[];
}

const normalizeConversationIds = (conversationIds: readonly string[]): string[] => {
    const normalized: string[] = [];
    const seen = new Set<string>();
    for (const conversationId of conversationIds) {
        if (!conversationId || seen.has(conversationId)) {
            continue;
        }
        seen.add(conversationId);
        normalized.push(conversationId);
    }
    return normalized;
};

const confirmConversationDelete = async (options: ConversationDeleteOperationOptions): Promise<boolean> => {
    if (options.confirm === false) {
        return true;
    }
    return await requireDialogsService().showConfirmation({
        title: i18n.t('chat.conversation.deleteTitle'),
        message: i18n.t('chat.conversation.deleteConfirm'),
        confirmText: i18n.t('common.delete'),
        variant: 'danger'
    });
};

const isDeleteProtected = (runtime: ChatConversationActionsControllerRuntime, conversationId: string): boolean => {
    return isProtectedEmptyConversation(runtime.state.getConversations(), conversationId, i18n.t('chat.conversation.newTitle'));
};

const forgetDeletedConversationUiState = (runtime: ChatConversationActionsControllerRuntime, conversationId: string): void => {
    runtime.conversationSettingsManager?.handleConversationDeleted?.(conversationId);
    runtime.uiManager.forgetConversationScrollPosition(conversationId);
    runtime.getComposerDraftManager()?.discardConversation(conversationId);
};

const applyDeletedActiveConversationFallback = async (runtime: ChatConversationActionsControllerRuntime, snapshot: ConversationDeleteFallbackSnapshot, deletedConversationIds: ReadonlySet<string>, activation: ConversationActivationSnapshot): Promise<void> => {
    try {
        if (!runtime.concurrencyScope.isConversationActivationSnapshotLive(activation)) {
            await runtime.host.view.renderConversationList();
            runtime.storageManager.saveChatState();
            return;
        }
        const fallbackConversationId = runtime.host.navigation.resolveConversationDeleteFallbackId(snapshot, deletedConversationIds);
        if (fallbackConversationId && runtime.state.hasConversation(fallbackConversationId)) {
            await activateConversationById(runtime, fallbackConversationId, { transferMode: 'restore' }, activation);
            return;
        }
        try {
            await createConversation(runtime, { transferMode: 'restore' }, activation);
        } catch (error) {
            const runtimeError = ensureError(error);
            if (runtime.concurrencyScope.isConversationActivationSnapshotLive(activation)) await clearConversationSelection(runtime);
            throw runtimeError;
        }
    } finally {
        runtime.uiManager.completeConversationTransition(activation.sequence);
    }
};

const finalizeDeleteUi = async (runtime: ChatConversationActionsControllerRuntime, inputArguments: { activation: ConversationActivationSnapshot | null; snapshot: ConversationDeleteFallbackSnapshot; deletedConversationIds: ReadonlySet<string> }): Promise<void> => {
    if (inputArguments.activation !== null) {
        await applyDeletedActiveConversationFallback(runtime, inputArguments.snapshot, inputArguments.deletedConversationIds, inputArguments.activation);
        return;
    }
    await runtime.host.view.refreshConversationsUI();
    runtime.storageManager.saveChatState();
};

const deleteConversationRecords = async (runtime: ChatConversationActionsControllerRuntime, conversationIds: readonly string[]): Promise<string[]> => {
    const deletableConversationIds: string[] = [];
    for (const conversationId of conversationIds) {
        if (!runtime.state.hasConversation(conversationId) || isDeleteProtected(runtime, conversationId)) {
            continue;
        }
        deletableConversationIds.push(conversationId);
    }
    const deletedConversationIds = [...(await runtime.conversationManager.deleteConversations(deletableConversationIds))];
    for (const conversationId of deletedConversationIds) forgetDeletedConversationUiState(runtime, conversationId);
    return deletedConversationIds;
};

const deleteConversations = async (runtime: ChatConversationActionsControllerRuntime, conversationIds: readonly string[], options: ConversationDeleteManyOperationOptions = {}): Promise<ConversationDeleteResult> => {
    const targetConversationIds = normalizeConversationIds(conversationIds).filter((conversationId) => runtime.state.hasConversation(conversationId));
    if (targetConversationIds.length === 0) {
        return { deletedConversationIds: [] };
    }
    await cancelConversationRename(runtime.host, runtime.state);
    if (!(await confirmConversationDelete(options))) {
        return { deletedConversationIds: [] };
    }
    const currentConversationId = runtime.state.getCurrentConversationId();
    const snapshot = runtime.host.navigation.captureConversationDeleteFallbackSnapshot(currentConversationId);
    const deletesActiveConversation = currentConversationId !== null && targetConversationIds.includes(currentConversationId);
    const activation = deletesActiveConversation ? runtime.concurrencyScope.beginConversationActivation() : null;
    if (activation !== null) runtime.uiManager.beginConversationTransition(activation.sequence);
    markLocalConversationDeletes(runtime, targetConversationIds);
    let deletedConversationIds: string[] = [];
    try {
        deletedConversationIds = await deleteConversationRecords(runtime, targetConversationIds);
    } catch (error) {
        if (activation !== null) runtime.uiManager.completeConversationTransition(activation.sequence);
        throw error;
    } finally {
        clearLocalConversationDeletes(runtime, targetConversationIds);
    }
    const deletedConversationIdSet = new Set(deletedConversationIds);
    const activeConversationDeleted = currentConversationId !== null && (deletedConversationIdSet.has(currentConversationId) || !runtime.state.hasConversation(currentConversationId));
    await finalizeDeleteUi(runtime, { activation: activeConversationDeleted ? activation : null, snapshot, deletedConversationIds: deletedConversationIdSet });
    if (!activeConversationDeleted && activation !== null) runtime.uiManager.completeConversationTransition(activation.sequence);
    if (options.notify !== false && deletedConversationIds.length > 0 && options.batchNotify !== true) {
        runtime.host.workflow.feedback.show(i18n.t('chat.conversation.deleted'), 'success');
    }
    return { deletedConversationIds };
};

const handleRemoteConversationDeleted = async (runtime: ChatConversationActionsControllerRuntime, conversationId: string): Promise<void> => {
    if (!conversationId) {
        return;
    }
    const wasLocalDeletePending = isLocalConversationDeletePending(runtime, conversationId);
    const currentConversationId = runtime.state.getCurrentConversationId();
    const snapshot = runtime.host.navigation.captureConversationDeleteFallbackSnapshot(currentConversationId);
    const activation = currentConversationId === conversationId && !wasLocalDeletePending ? runtime.concurrencyScope.beginConversationActivation() : null;
    if (activation !== null) runtime.uiManager.beginConversationTransition(activation.sequence);
    const conversationWasKnown = runtime.state.hasConversation(conversationId);
    if (conversationWasKnown) {
        forgetDeletedConversationUiState(runtime, conversationId);
        runtime.conversationManager.forgetConversation(conversationId);
    }
    if (wasLocalDeletePending) {
        await runtime.host.view.renderConversationList();
        runtime.storageManager.saveChatState(true);
        return;
    }
    const deletedConversationIds = new Set([conversationId]);
    await finalizeDeleteUi(runtime, { activation, snapshot, deletedConversationIds });
};

export { deleteConversations, handleRemoteConversationDeleted };
export type { ConversationDeleteManyOperationOptions, ConversationDeleteResult };
