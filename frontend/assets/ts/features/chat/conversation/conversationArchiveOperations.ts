/* SoAI - Chat feature conversation archive operations [frontend/assets/ts/features/chat/conversation/conversationArchiveOperations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { applyConversationMetadataSnapshot, parseConversationRecordForId } from '@features/chat/conversation/conversationPersistenceSnapshots.ts';
import type { ConversationMetadataOperationDependencies } from '@features/chat/conversation/conversationMetadataOperationDeps.ts';
import { requireConversationId } from '@features/chat/validation/ids.ts';

const setConversationArchived = async (dependencies: ConversationMetadataOperationDependencies, conversationId: string, isArchived: boolean): Promise<void> => {
    const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
    const conversation = dependencies.conversations.get(normalizedConversationId);
    if (!conversation) return;
    const currentArchived = conversation.isArchived === true;
    if (currentArchived === isArchived) {
        return;
    }
    const previousArchived = conversation.isArchived === true;
    const mutationVersion = dependencies.mutationSequencer.begin(normalizedConversationId, 'archived');
    let expectedUpdatedAt = conversation.updatedAt;
    conversation.isArchived = isArchived;
    dependencies.conversations.set(normalizedConversationId, conversation);
    try {
        await dependencies.ensureConversationPersisted(conversation);
        if (!dependencies.mutationSequencer.isCurrent(normalizedConversationId, 'archived', mutationVersion) || dependencies.conversations.get(normalizedConversationId) !== conversation || conversation.isArchived !== isArchived) {
            return;
        }
        expectedUpdatedAt = conversation.updatedAt;
        const updated = await dependencies.chatApi.updateArchived(normalizedConversationId, isArchived);
        if (!dependencies.mutationSequencer.isCurrent(normalizedConversationId, 'archived', mutationVersion) || dependencies.conversations.get(normalizedConversationId) !== conversation) {
            return;
        }
        if (!applyConversationMetadataSnapshot(conversation, parseConversationRecordForId(updated, normalizedConversationId, 'Updated conversation archived payload'))) {
            return;
        }
        if (isArchived && dependencies.getCurrentConversationId() !== normalizedConversationId) {
            dependencies.conversations.delete(normalizedConversationId);
        } else {
            dependencies.conversations.set(normalizedConversationId, conversation);
        }
    } catch (error) {
        if (!dependencies.mutationSequencer.isCurrent(normalizedConversationId, 'archived', mutationVersion) || dependencies.conversations.get(normalizedConversationId) !== conversation || conversation.isArchived !== isArchived || conversation.updatedAt !== expectedUpdatedAt) {
            return;
        }
        conversation.isArchived = previousArchived;
        dependencies.conversations.set(normalizedConversationId, conversation);
        throw error;
    }
};

const ensureConversationLoaded = async (dependencies: ConversationMetadataOperationDependencies, conversationId: string): Promise<void> => {
    const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
    if (dependencies.conversations.has(normalizedConversationId)) {
        return;
    }
    const response = await dependencies.chatApi.get(normalizedConversationId);
    const conversation = parseConversationRecordForId(response, normalizedConversationId, 'Loaded conversation payload');
    conversation.messagesHydrated = false;
    dependencies.conversations.set(normalizedConversationId, conversation);
    dependencies.markConversationPersisted(normalizedConversationId);
};

export { ensureConversationLoaded, setConversationArchived };
