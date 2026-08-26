/* SoAI - Archived conversations modal mutations [frontend/assets/ts/pages/chat/controllers/modals/archivedconversations/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { limitConversationTitleLength, sanitizeTitle } from '@features/chat/public.ts';
import type { ArchivedConversationsModalHost, ArchivedConversationsModalState } from '@pages/chat/controllers/modals/archivedconversations/types.ts';
import { resolveArchivedConversationDeleteConfirmation } from '@pages/chat/controllers/modals/archivedconversations/actions.ts';

const invalidateArchivedConversationRequests = (state: ArchivedConversationsModalState): void => {
    state.requestVersion += 1;
    state.loading = false;
};

const requireArchivedConversation = (state: ArchivedConversationsModalState, conversationId: string): ArchivedConversationsModalState['conversations'][number] => {
    const conversation = state.conversations.find((entry) => entry.id === conversationId) ?? null;
    if (!conversation) {
        throw new Error(`Archived conversation is not loaded in the modal: ${conversationId}`);
    }
    return conversation;
};

const removeArchivedConversation = (state: ArchivedConversationsModalState, conversationId: string): void => {
    const previousLength = state.conversations.length;
    state.conversations = state.conversations.filter((conversation) => conversation.id !== conversationId);
    state.selectedIds.delete(conversationId);
    if (state.conversations.length !== previousLength) {
        state.totalCount = Math.max(0, state.totalCount - 1);
    }
};

const unarchiveConversation = async (host: ArchivedConversationsModalHost, state: ArchivedConversationsModalState, conversationId: string): Promise<void> => {
    requireArchivedConversation(state, conversationId);
    invalidateArchivedConversationRequests(state);
    await host.api.webui.chat.updateArchived(conversationId, false);
    removeArchivedConversation(state, conversationId);
    await host.refreshSidebarConversationList();
};

const deleteArchivedConversation = async (host: ArchivedConversationsModalHost, state: ArchivedConversationsModalState, conversationId: string): Promise<void> => {
    requireArchivedConversation(state, conversationId);
    const confirmed = await requireDialogsService().showConfirmation({
        ...resolveArchivedConversationDeleteConfirmation('archive:delete', 1),
        confirmText: i18n.t('common.delete'),
        variant: 'danger'
    });
    if (!confirmed) {
        return;
    }
    invalidateArchivedConversationRequests(state);
    const deletedConversationIds = await host.deleteArchivedConversations([conversationId]);
    for (const deletedConversationId of deletedConversationIds) {
        removeArchivedConversation(state, deletedConversationId);
    }
};

const toggleArchivedConversationFavorite = async (host: ArchivedConversationsModalHost, state: ArchivedConversationsModalState, conversationId: string): Promise<void> => {
    const conversation = requireArchivedConversation(state, conversationId);
    invalidateArchivedConversationRequests(state);
    await host.api.webui.chat.updateFavorite(conversationId, !conversation.isFavorite);
    conversation.isFavorite = !conversation.isFavorite;
};

const updateArchivedConversationColor = async (host: ArchivedConversationsModalHost, state: ArchivedConversationsModalState, conversationId: string, color: string): Promise<void> => {
    const conversation = requireArchivedConversation(state, conversationId);
    invalidateArchivedConversationRequests(state);
    await host.api.webui.chat.updateColor(conversationId, color);
    conversation.color = color;
};

const startArchivedConversationRename = (state: ArchivedConversationsModalState, conversationId: string): void => {
    const conversation = requireArchivedConversation(state, conversationId);
    state.renamingId = conversationId;
    state.renameDraft = limitConversationTitleLength(sanitizeTitle(conversation.title));
};

const saveArchivedConversationRename = async (host: ArchivedConversationsModalHost, state: ArchivedConversationsModalState, conversationId: string): Promise<void> => {
    if (state.renamingId !== conversationId) {
        throw new Error('Archived conversation rename save does not match the active rename id');
    }
    const conversation = requireArchivedConversation(state, conversationId);
    const title = sanitizeTitle(limitConversationTitleLength(state.renameDraft));
    invalidateArchivedConversationRequests(state);
    await host.api.webui.chat.updateTitle(conversationId, title);
    conversation.title = title;
    state.renamingId = null;
};

const batchUnarchiveConversations = async (host: ArchivedConversationsModalHost, state: ArchivedConversationsModalState): Promise<void> => {
    if (state.selectedIds.size === 0) {
        throw new Error('Archived conversation batch unarchive requires a selection');
    }
    for (const conversationId of state.selectedIds) {
        requireArchivedConversation(state, conversationId);
    }
    invalidateArchivedConversationRequests(state);
    for (const conversationId of [...state.selectedIds]) {
        await host.api.webui.chat.updateArchived(conversationId, false);
        removeArchivedConversation(state, conversationId);
    }
    await host.refreshSidebarConversationList();
    state.selectionActive = false;
    state.selectedIds.clear();
};

const batchDeleteArchivedConversations = async (host: ArchivedConversationsModalHost, state: ArchivedConversationsModalState): Promise<void> => {
    if (state.selectedIds.size === 0) {
        throw new Error('Archived conversation batch delete requires a selection');
    }
    for (const conversationId of state.selectedIds) {
        requireArchivedConversation(state, conversationId);
    }
    const confirmed = await requireDialogsService().showConfirmation({
        ...resolveArchivedConversationDeleteConfirmation('archive:batch-delete', state.selectedIds.size),
        confirmText: i18n.t('common.delete'),
        variant: 'danger'
    });
    if (!confirmed) {
        return;
    }
    invalidateArchivedConversationRequests(state);
    const deletedConversationIds = await host.deleteArchivedConversations([...state.selectedIds]);
    for (const conversationId of deletedConversationIds) {
        removeArchivedConversation(state, conversationId);
    }
    state.selectionActive = false;
    state.selectedIds.clear();
};

export { batchDeleteArchivedConversations, batchUnarchiveConversations, deleteArchivedConversation, saveArchivedConversationRename, startArchivedConversationRename, toggleArchivedConversationFavorite, unarchiveConversation, updateArchivedConversationColor };
