/* SoAI - Chat conversation title mutation operations [frontend/assets/ts/features/chat/conversation/conversationTitleOperations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { applyConversationMetadataSnapshot, parseConversationRecordForId, requireConversationStateEntry } from '@features/chat/conversation/conversationPersistenceSnapshots.ts';
import type { ConversationMetadataOperationDependencies } from '@features/chat/conversation/conversationMetadataOperationDeps.ts';
import { requireConversationTitle } from '@features/chat/storage/conversationPayloadParsing.ts';
import { requireConversationId } from '@features/chat/validation/ids.ts';

const updateConversationTitle = async (dependencies: ConversationMetadataOperationDependencies, conversationId: string, title: string): Promise<void> => {
    const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
    const conversation = requireConversationStateEntry(dependencies.conversations, normalizedConversationId);
    const normalizedTitle = requireConversationTitle(title, 'Conversation');
    if (conversation.title === normalizedTitle) {
        return;
    }
    const previousTitle = conversation.title;
    const mutationVersion = dependencies.mutationSequencer.begin(normalizedConversationId, 'title');
    let expectedUpdatedAt = conversation.updatedAt;
    conversation.title = normalizedTitle;
    dependencies.conversations.set(normalizedConversationId, conversation);
    try {
        await dependencies.ensureConversationPersisted(conversation);
        if (!dependencies.mutationSequencer.isCurrent(normalizedConversationId, 'title', mutationVersion) || dependencies.conversations.get(normalizedConversationId) !== conversation || conversation.title !== normalizedTitle) {
            return;
        }
        expectedUpdatedAt = conversation.updatedAt;
        const updated = await dependencies.chatApi.updateTitle(normalizedConversationId, normalizedTitle);
        if (!dependencies.mutationSequencer.isCurrent(normalizedConversationId, 'title', mutationVersion) || dependencies.conversations.get(normalizedConversationId) !== conversation) {
            return;
        }
        applyConversationMetadataSnapshot(conversation, parseConversationRecordForId(updated, normalizedConversationId, 'Updated conversation title payload'));
        dependencies.conversations.set(normalizedConversationId, conversation);
    } catch (error) {
        if (!dependencies.mutationSequencer.isCurrent(normalizedConversationId, 'title', mutationVersion) || dependencies.conversations.get(normalizedConversationId) !== conversation || conversation.title !== normalizedTitle || conversation.updatedAt !== expectedUpdatedAt) {
            return;
        }
        conversation.title = previousTitle;
        dependencies.conversations.set(normalizedConversationId, conversation);
        throw error;
    }
};

export { updateConversationTitle };
