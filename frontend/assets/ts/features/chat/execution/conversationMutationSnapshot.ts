/* SoAI - Conversation mutation rollback snapshots for chat execution flows [frontend/assets/ts/features/chat/execution/conversationMutationSnapshot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasOwn, isNumber } from '@core/typeGuards.ts';
import type { ConversationContract, ConversationMessage } from '@features/chat/ChatTypes.ts';

interface ConversationMutationSnapshot {
    messages: ConversationMessage[];
    title: string | undefined;
    hasTitle: boolean;
    modelSettings: ConversationContract['modelSettings'];
    hasModelSettings: boolean;
    updatedAt: number | undefined;
    hasUpdatedAt: boolean;
}

const hasConversationField = (conversation: ConversationContract, field: string): boolean => hasOwn(conversation, field);

const resolveRestoredUpdatedAt = (conversation: ConversationContract, snapshot: ConversationMutationSnapshot): number | undefined => {
    const currentUpdatedAt = conversation.updatedAt;
    if (isNumber(currentUpdatedAt) && Number.isFinite(currentUpdatedAt) && isNumber(snapshot.updatedAt) && Number.isFinite(snapshot.updatedAt)) {
        return Math.max(currentUpdatedAt, snapshot.updatedAt);
    }
    return snapshot.updatedAt;
};

const captureConversationMutationSnapshot = (conversation: ConversationContract): ConversationMutationSnapshot => {
    return {
        messages: [...conversation.messages],
        title: conversation.title,
        hasTitle: hasConversationField(conversation, 'title'),
        modelSettings: conversation.modelSettings,
        hasModelSettings: hasConversationField(conversation, 'modelSettings'),
        updatedAt: conversation.updatedAt,
        hasUpdatedAt: hasConversationField(conversation, 'updatedAt')
    };
};

const restoreConversationMutationSnapshot = (conversation: ConversationContract, snapshot: ConversationMutationSnapshot): void => {
    conversation.messages = snapshot.messages;
    if (snapshot.hasTitle) {
        if (snapshot.title === undefined) {
            delete conversation['title'];
        } else {
            conversation.title = snapshot.title;
        }
    } else {
        delete conversation['title'];
    }
    if (snapshot.hasModelSettings) {
        if (snapshot.modelSettings === undefined) {
            delete conversation.modelSettings;
        } else {
            conversation.modelSettings = snapshot.modelSettings;
        }
    } else {
        delete conversation.modelSettings;
    }
    if (snapshot.hasUpdatedAt) {
        const updatedAt = resolveRestoredUpdatedAt(conversation, snapshot);
        if (updatedAt === undefined) {
            delete conversation.updatedAt;
        } else {
            conversation.updatedAt = updatedAt;
        }
    } else {
        delete conversation.updatedAt;
    }
};

export { captureConversationMutationSnapshot, restoreConversationMutationSnapshot };
export type { ConversationMutationSnapshot };
