/* SoAI - Chat page conversation list ordering and fallback policy [frontend/assets/ts/pages/chat/controllers/page/conversationListOrderingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseConversationId } from '@core/chat/conversationIdentifier.ts';
import { i18n } from '@core/i18n/index.ts';
import { matchesSearchFilterQuery } from '@core/search/searchQuery.ts';
import { compareConversationRecency, isMessagingAccountConversation, resolveConversationDisplayTitleFromConversation, type Conversation } from '@features/chat/public.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatViewStateHost } from '@pages/chat/state/ChatViewStateManager.ts';
import type { ConversationDeleteFallbackSnapshot } from '@pages/chat/controllers/chatconversationactionscontroller/contracts.ts';
import type { ChatConversationRuntime } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';

interface ConversationListOrderingHost extends ChatConversationStateHost, ChatSettingsStateHost, ChatViewStateHost {
    conversationRuntime: ChatConversationRuntime;
}

interface ConversationListFilters {
    hideAutomationRuns: boolean;
    hideMessagingConversations: boolean;
}

const UNFILTERED_CONVERSATION_LIST_FILTERS: ConversationListFilters = {
    hideAutomationRuns: false,
    hideMessagingConversations: false
};

const compareVisibleConversationOrder = (host: ConversationListOrderingHost, left: Conversation, right: Conversation): number => {
    if (host.viewState.showFavoritesAtTop) {
        const leftFavorite = left.isFavorite === true;
        const rightFavorite = right.isFavorite === true;
        if (leftFavorite && !rightFavorite) {
            return -1;
        }
        if (!leftFavorite && rightFavorite) {
            return 1;
        }
    }
    return compareConversationRecency(left, right);
};

const conversationMatchesSearch = (host: ConversationListOrderingHost, conversation: Conversation, referencedConversationId: string | null): boolean => {
    const query = host.viewState.searchQueryLower;
    if (!query) {
        return true;
    }
    const renameConversationId = host.conversationState.conversationRenameState?.scope === 'sidebar' ? host.conversationState.conversationRenameState.conversationId : null;
    if (renameConversationId === conversation.id) {
        return true;
    }
    if (referencedConversationId !== null) {
        return referencedConversationId === conversation.id;
    }
    const title = resolveConversationDisplayTitleFromConversation(conversation, i18n.t('chat.conversation.untitled'));
    if (matchesSearchFilterQuery(title, query)) {
        return true;
    }
    const messageManager = host.conversationRuntime.requireMessages();
    for (const message of conversation.messages) {
        for (const fragment of messageManager.getMessageTextFragments(message)) {
            if (matchesSearchFilterQuery(fragment, query)) {
                return true;
            }
        }
    }
    return false;
};

const resolveActiveConversationListFilters = (host: ConversationListOrderingHost): ConversationListFilters => {
    return {
        hideAutomationRuns: host.settings.parameters.hideAutomationRuns === true,
        hideMessagingConversations: host.settings.parameters.hideMessagingConversations === true
    };
};

const passesConversationListFilters = (conversation: Conversation, filters: ConversationListFilters): boolean => {
    if (filters.hideAutomationRuns && conversation.isAutomation === true) {
        return false;
    }
    return !(filters.hideMessagingConversations && isMessagingAccountConversation(conversation));
};

const isVisibleConversation = (host: ConversationListOrderingHost, conversation: Conversation, filters: ConversationListFilters, referencedConversationId: string | null): boolean => {
    if (conversation.isArchived === true) {
        return false;
    }
    if (referencedConversationId === null && !passesConversationListFilters(conversation, filters)) {
        return false;
    }
    return conversationMatchesSearch(host, conversation, referencedConversationId);
};

const resolveSidebarConversationOrder = (host: ConversationListOrderingHost): Conversation[] => {
    const filters = resolveActiveConversationListFilters(host);
    const referencedConversationId = parseConversationId(host.viewState.searchQuery);
    const conversations = Array.from(host.conversationState.conversations.values()).filter((conversation) => isVisibleConversation(host, conversation, filters, referencedConversationId));
    conversations.sort((left, right) => compareVisibleConversationOrder(host, left, right));
    return conversations;
};

const resolveUnarchivedConversationIdsByRecency = (conversations: ReadonlyMap<string, Conversation>, filters: ConversationListFilters): string[] => {
    const ordered = Array.from(conversations.values()).filter((conversation) => {
        if (conversation.isArchived === true) {
            return false;
        }
        return passesConversationListFilters(conversation, filters);
    });
    ordered.sort(compareConversationRecency);
    return ordered.map((conversation) => conversation.id);
};

const captureConversationDeleteFallbackSnapshot = (host: ConversationListOrderingHost, activeConversationId: string | null): ConversationDeleteFallbackSnapshot => {
    return {
        activeConversationId,
        visibleConversationIds: resolveSidebarConversationOrder(host).map((conversation) => conversation.id),
        preferredUnarchivedConversationIds: resolveUnarchivedConversationIdsByRecency(host.conversationState.conversations, resolveActiveConversationListFilters(host)),
        allUnarchivedConversationIds: resolveUnarchivedConversationIdsByRecency(host.conversationState.conversations, UNFILTERED_CONVERSATION_LIST_FILTERS)
    };
};

const firstRemainingId = (conversationIds: readonly string[], deletedConversationIds: ReadonlySet<string>, conversations: ReadonlyMap<string, Conversation>): string | null => {
    for (const conversationId of conversationIds) {
        if (!deletedConversationIds.has(conversationId) && conversations.has(conversationId)) {
            return conversationId;
        }
    }
    return null;
};

const resolveVisibleNeighborFallback = (snapshot: ConversationDeleteFallbackSnapshot, deletedConversationIds: ReadonlySet<string>, conversations: ReadonlyMap<string, Conversation>): string | null => {
    if (snapshot.activeConversationId === null) {
        return null;
    }
    const activeIndex = snapshot.visibleConversationIds.indexOf(snapshot.activeConversationId);
    if (activeIndex < 0) {
        return null;
    }
    for (let index = activeIndex - 1; index >= 0; index -= 1) {
        const conversationId = snapshot.visibleConversationIds[index];
        if (conversationId !== undefined && !deletedConversationIds.has(conversationId) && conversations.has(conversationId)) {
            return conversationId;
        }
    }
    for (let index = activeIndex + 1; index < snapshot.visibleConversationIds.length; index += 1) {
        const conversationId = snapshot.visibleConversationIds[index];
        if (conversationId !== undefined && !deletedConversationIds.has(conversationId) && conversations.has(conversationId)) {
            return conversationId;
        }
    }
    return null;
};

const resolveConversationDeleteFallbackId = (snapshot: ConversationDeleteFallbackSnapshot, deletedConversationIds: ReadonlySet<string>, conversations: ReadonlyMap<string, Conversation>): string | null => {
    const visibleNeighborId = resolveVisibleNeighborFallback(snapshot, deletedConversationIds, conversations);
    if (visibleNeighborId !== null) {
        return visibleNeighborId;
    }
    return firstRemainingId(snapshot.preferredUnarchivedConversationIds, deletedConversationIds, conversations) ?? firstRemainingId(snapshot.allUnarchivedConversationIds, deletedConversationIds, conversations);
};

export { captureConversationDeleteFallbackSnapshot, resolveConversationDeleteFallbackId, resolveSidebarConversationOrder };
export type { ConversationDeleteFallbackSnapshot, ConversationListOrderingHost };
