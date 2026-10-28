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
    if (conversation.title === normalizedTitle && conversation.committedTitleMetadata?.title === normalizedTitle && conversation.committedTitleMetadata.autoUpdateAllowed === false) {
        return;
    }
    const previousTitle = conversation.title;
    const previousAuthority = conversation.titleAutoUpdateAllowed;
    if (!conversation.committedTitleMetadata && previousAuthority !== undefined) conversation.committedTitleMetadata = { title: previousTitle, autoUpdateAllowed: previousAuthority, updatedAt: conversation.updatedAt };
    let expectedObservation = conversation.committedTitleMetadata;
    const mutationVersion = dependencies.mutationSequencer.begin(normalizedConversationId, 'title');
    conversation.title = normalizedTitle;
    conversation.titleAutoUpdateAllowed = false;
    dependencies.conversations.set(normalizedConversationId, conversation);
    try {
        await dependencies.ensureConversationPersisted(conversation);
        if (!dependencies.mutationSequencer.isCurrent(normalizedConversationId, 'title', mutationVersion) || dependencies.conversations.get(normalizedConversationId) !== conversation) {
            return;
        }
        expectedObservation = conversation.committedTitleMetadata;
        const updated = await dependencies.chatApi.updateTitle(normalizedConversationId, normalizedTitle);
        if (!dependencies.mutationSequencer.isCurrent(normalizedConversationId, 'title', mutationVersion) || dependencies.conversations.get(normalizedConversationId) !== conversation) {
            return;
        }
        applyConversationMetadataSnapshot(conversation, parseConversationRecordForId(updated, normalizedConversationId, 'Updated conversation title payload'));
        dependencies.conversations.set(normalizedConversationId, conversation);
    } catch (error) {
        if (!dependencies.mutationSequencer.isCurrent(normalizedConversationId, 'title', mutationVersion) || dependencies.conversations.get(normalizedConversationId) !== conversation) {
            return;
        }
        if (conversation.title === normalizedTitle && conversation.titleAutoUpdateAllowed === false && conversation.committedTitleMetadata === expectedObservation) {
            const committed = conversation.committedTitleMetadata;
            conversation.title = committed?.title ?? previousTitle;
            const authority = committed?.autoUpdateAllowed ?? previousAuthority;
            if (authority === undefined) delete conversation.titleAutoUpdateAllowed;
            else conversation.titleAutoUpdateAllowed = authority;
            dependencies.conversations.set(normalizedConversationId, conversation);
        }
        throw error;
    }
};

export { updateConversationTitle };
