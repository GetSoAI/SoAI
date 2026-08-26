/* SoAI - Chat feature conversation selection policy [frontend/assets/ts/features/chat/conversation/conversationSelectionPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isMessagingAccountConversation } from '@features/chat/conversation/conversationSettingsEligibility.ts';
import { isConversationEmpty } from '@features/chat/conversationFormatting.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';

const compareConversationRecency = (left: Conversation, right: Conversation): number => {
    const updatedDiff = right.updatedAt - left.updatedAt;
    if (updatedDiff !== 0) {
        return updatedDiff;
    }
    const createdDiff = right.createdAt - left.createdAt;
    if (createdDiff !== 0) {
        return createdDiff;
    }
    return left.id.localeCompare(right.id, 'en');
};

const resolveMostRecentConversation = (conversations: ReadonlyMap<string, Conversation>): Conversation | null => {
    let mostRecentConversation: Conversation | null = null;
    for (const conversation of conversations.values()) {
        if (mostRecentConversation === null || compareConversationRecency(conversation, mostRecentConversation) < 0) {
            mostRecentConversation = conversation;
        }
    }
    return mostRecentConversation;
};

const isReusableNewConversation = (conversation: Conversation, defaultTitle: string): boolean => {
    if (conversation.isArchived === true || conversation.isAutomation === true || isMessagingAccountConversation(conversation)) {
        return false;
    }
    return isConversationEmpty(conversation, defaultTitle);
};

const resolveReusableNewConversationId = (conversations: ReadonlyMap<string, Conversation>, defaultTitle: string): string | null => {
    const mostRecentConversation = resolveMostRecentConversation(conversations);
    if (mostRecentConversation === null || !isReusableNewConversation(mostRecentConversation, defaultTitle)) {
        return null;
    }
    return mostRecentConversation.id;
};

export { compareConversationRecency, resolveMostRecentConversation, resolveReusableNewConversationId };
