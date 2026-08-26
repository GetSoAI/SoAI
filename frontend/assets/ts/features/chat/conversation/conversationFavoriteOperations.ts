/* SoAI - Chat feature conversation favorite operations [frontend/assets/ts/features/chat/conversation/conversationFavoriteOperations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationMetadataOperationDependencies } from '@features/chat/conversation/conversationMetadataOperationDeps.ts';
import { applyConversationMetadataSnapshot, parseConversationRecordForId } from '@features/chat/conversation/conversationPersistenceSnapshots.ts';
import { requireConversationId } from '@features/chat/validation/ids.ts';

const toggleConversationFavorite = async (dependencies: ConversationMetadataOperationDependencies, conversationId: string): Promise<void> => {
    const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
    const conversation = dependencies.conversations.get(normalizedConversationId);
    if (!conversation) return;
    const newFavorite = conversation.isFavorite !== true;
    const previousFavorite = conversation.isFavorite;
    const mutationVersion = dependencies.mutationSequencer.begin(normalizedConversationId, 'favorite');
    let expectedUpdatedAt = conversation.updatedAt;
    conversation.isFavorite = newFavorite;
    dependencies.conversations.set(normalizedConversationId, conversation);
    try {
        await dependencies.ensureConversationPersisted(conversation);
        if (!dependencies.mutationSequencer.isCurrent(normalizedConversationId, 'favorite', mutationVersion) || dependencies.conversations.get(normalizedConversationId) !== conversation || conversation.isFavorite !== newFavorite) {
            return;
        }
        expectedUpdatedAt = conversation.updatedAt;
        const updated = await dependencies.chatApi.updateFavorite(normalizedConversationId, newFavorite);
        if (!dependencies.mutationSequencer.isCurrent(normalizedConversationId, 'favorite', mutationVersion) || dependencies.conversations.get(normalizedConversationId) !== conversation) {
            return;
        }
        applyConversationMetadataSnapshot(conversation, parseConversationRecordForId(updated, normalizedConversationId, 'Updated conversation favorite payload'));
        dependencies.conversations.set(normalizedConversationId, conversation);
    } catch (error) {
        if (!dependencies.mutationSequencer.isCurrent(normalizedConversationId, 'favorite', mutationVersion) || dependencies.conversations.get(normalizedConversationId) !== conversation || conversation.isFavorite !== newFavorite || conversation.updatedAt !== expectedUpdatedAt) {
            return;
        }
        conversation.isFavorite = previousFavorite;
        dependencies.conversations.set(normalizedConversationId, conversation);
        throw error;
    }
};

export { toggleConversationFavorite };
