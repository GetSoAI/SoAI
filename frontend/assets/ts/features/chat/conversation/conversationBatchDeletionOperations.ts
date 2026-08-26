/* SoAI - Chat conversation batch deletion operations [frontend/assets/ts/features/chat/conversation/conversationBatchDeletionOperations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationBatchDeleteResponse } from '@core/api/contracts/webuiConversationContracts.ts';
import { isConversationEmpty } from '@features/chat/conversationFormatting.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';
import { requireConversationId } from '@features/chat/validation/ids.ts';

interface ConversationBatchDeletionDependencies {
    chatApi: { batchDelete(conversationIds: readonly string[]): Promise<ConversationBatchDeleteResponse> };
    conversations: Map<string, Conversation>;
    persistedConversationIds: Set<string>;
    persistingConversationById: ReadonlyMap<string, Promise<void>>;
    deletedWhilePersistingConversationIds: Set<string>;
    forgetConversation(conversationId: string): void;
    getDefaultTitle(): string;
}

const normalizeConversationIds = (conversationIds: readonly string[]): string[] => {
    const normalizedIds: string[] = [];
    const seen = new Set<string>();
    for (const conversationId of conversationIds) {
        const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
        if (seen.has(normalizedConversationId)) {
            continue;
        }
        seen.add(normalizedConversationId);
        normalizedIds.push(normalizedConversationId);
    }
    return normalizedIds;
};

const deleteConversations = async (dependencies: ConversationBatchDeletionDependencies, conversationIds: readonly string[]): Promise<readonly string[]> => {
    const localDeletedIds: string[] = [];
    const persistedIds: string[] = [];
    for (const conversationId of normalizeConversationIds(conversationIds)) {
        const conversation = dependencies.conversations.get(conversationId) ?? null;
        if (conversation && dependencies.conversations.size === 1 && isConversationEmpty(conversation, dependencies.getDefaultTitle())) {
            continue;
        }
        if (dependencies.persistingConversationById.has(conversationId)) {
            dependencies.deletedWhilePersistingConversationIds.add(conversationId);
        }
        if (dependencies.persistedConversationIds.has(conversationId)) {
            persistedIds.push(conversationId);
            continue;
        }
        if (conversation) {
            localDeletedIds.push(conversationId);
        }
    }
    let serverDeletedIds: readonly string[] = [];
    if (persistedIds.length > 0) {
        serverDeletedIds = (await dependencies.chatApi.batchDelete(persistedIds)).deletedIds;
    }
    const deletedIds = [...localDeletedIds, ...serverDeletedIds];
    for (const conversationId of deletedIds) {
        dependencies.forgetConversation(conversationId);
    }
    return deletedIds;
};

export { deleteConversations };
export type { ConversationBatchDeletionDependencies };
