/* SoAI - In-place user message edit resubmission flow [frontend/assets/ts/features/chat/message/messageEditCommit.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationExecutionRunResult } from '@core/chat/protocols.ts';
import { cloneStructured } from '@core/primitives/clone.ts';
import { isNumber, isObject } from '@core/typeGuards.ts';
import type { ChatMessage, ConversationContract, ConversationMessage } from '@features/chat/ChatTypes.ts';
import type { ChatStreamResponseOptions } from '@features/chat/chatstreamservice/types.ts';
import { captureConversationMutationSnapshot, restoreConversationMutationSnapshot } from '@features/chat/execution/conversationMutationSnapshot.ts';
import { applyPrimaryChatExecutionModelToConversation, requireChatExecutionModelPreflight, requireNoActiveConversationExecution } from '@features/chat/modelExecutionPreflight.ts';
import { applyEditedUserText, removeEditedUserAttachmentIndexes } from '@features/chat/message/messageEditing.ts';
import { isUserMessageRole } from '@features/chat/message/messageRole.ts';
import { resolvePersistedMessageCursor } from '@features/chat/message/persistedMessageIdentity.ts';
import type { MessageReferenceResolver } from '@features/chat/message/messageReferenceResolution.ts';
import type { ChatStorageMessageRecord, LoadConversationMessagesOptions } from '@features/chat/storage/storageModels.ts';
import { requireConversationId } from '@features/chat/validation/ids.ts';

type ChatMessageEditCommitDependencies = {
    getCurrentConversation: () => ConversationContract | null;
    getCurrentModel: () => string | null;
    getModelStreamHasPayload: () => boolean;
    isModelAvailable: (modelId: string) => boolean;
    resolveMessageReference: MessageReferenceResolver;
    saveAndSync: (conversation: ConversationContract) => Promise<void>;
    loadConversationMessages: (conversationId: string, options?: LoadConversationMessagesOptions) => Promise<void>;
    commitPendingDeletesForConversation: (conversation: ConversationContract) => Promise<void>;
    runConversationExecutionIfIdle: (conversationId: string, task: () => Promise<void>) => Promise<ConversationExecutionRunResult>;
    invalidateChatMarkup: (scope: 'current' | 'list' | 'both') => void;
    renderCurrentConversation: () => Promise<void>;
    refreshConversationsUI: () => Promise<void>;
    streamResponse: (conversation: ConversationContract, options?: ChatStreamResponseOptions) => Promise<void>;
    isConversationExecuting: (conversationId: string) => boolean;
    resubmitUserMessage: (conversation: ConversationContract, inputArguments: { createdAtMs: number; messageId: number; message: ChatStorageMessageRecord }) => Promise<void>;
};

const resolveMessageTimestamp = (message: ConversationMessage | null | undefined): number | null => {
    if (!isObject(message)) {
        return null;
    }
    const timestamp = message['timestamp'];
    return isNumber(timestamp) && Number.isFinite(timestamp) && Number.isInteger(timestamp) && timestamp >= 0 ? timestamp : null;
};

const isServerWindowedConversation = (conversation: ConversationContract): boolean => {
    return conversation.history !== undefined;
};

const commitChatMessageResubmissionInConversation = async (dependencies: ChatMessageEditCommitDependencies, inputArguments: { conversation: ConversationContract; conversationId: string; messageId: string; updatedText: string | null; removedAttachmentIndexes: readonly number[]; onCommitted: (() => void) | null }): Promise<void> => {
    const initialReference = dependencies.resolveMessageReference(inputArguments.conversation, inputArguments.messageId);
    const initialMessage = initialReference.message;
    if (!initialMessage || !isUserMessageRole(initialMessage) || initialReference.index < 0) {
        return;
    }

    requireChatExecutionModelPreflight({
        conversation: inputArguments.conversation,
        selectedModelId: dependencies.getCurrentModel(),
        modelStreamHasPayload: dependencies.getModelStreamHasPayload(),
        isModelAvailable: (modelId) => dependencies.isModelAvailable(modelId)
    });
    await dependencies.commitPendingDeletesForConversation(inputArguments.conversation);
    requireNoActiveConversationExecution({ conversationId: inputArguments.conversationId, isConversationExecuting: (candidateConversationId) => dependencies.isConversationExecuting(candidateConversationId), context: 'Chat message edit' });

    const conversation = dependencies.getCurrentConversation();
    if (conversation !== inputArguments.conversation || requireConversationId(conversation.id, 'Conversation') !== inputArguments.conversationId) {
        return;
    }

    const targetIndex = conversation.messages.indexOf(initialMessage);
    if (targetIndex < 0) {
        return;
    }
    const modelPreflight = requireChatExecutionModelPreflight({
        conversation,
        selectedModelId: dependencies.getCurrentModel(),
        modelStreamHasPayload: dependencies.getModelStreamHasPayload(),
        isModelAvailable: (modelId) => dependencies.isModelAvailable(modelId)
    });
    const mutationSnapshot = captureConversationMutationSnapshot(conversation);
    let committed = false;
    try {
        const editedMessage: ChatMessage = cloneStructured(initialMessage);
        removeEditedUserAttachmentIndexes(editedMessage, inputArguments.removedAttachmentIndexes);
        if (inputArguments.updatedText !== null) {
            applyEditedUserText(editedMessage, inputArguments.updatedText);
        }
        const preservedTimestamp = resolveMessageTimestamp(initialMessage);
        if (preservedTimestamp === null) {
            throw new Error('Edited user message timestamp is invalid.');
        }
        editedMessage.timestamp = preservedTimestamp;
        const editedRecord: ChatStorageMessageRecord = { ...editedMessage, role: editedMessage.role, timestamp: preservedTimestamp };
        applyPrimaryChatExecutionModelToConversation(conversation, modelPreflight.primaryModelId);
        conversation.messages = [...conversation.messages.slice(0, targetIndex), editedMessage];
        if (isServerWindowedConversation(conversation)) {
            const cursor = resolvePersistedMessageCursor(initialMessage);
            if (cursor === null) {
                throw new Error('Edited persisted user message cursor is missing.');
            }
            await dependencies.resubmitUserMessage(conversation, {
                createdAtMs: cursor.createdAtMs,
                messageId: cursor.id,
                message: editedRecord
            });
        } else {
            await dependencies.saveAndSync(conversation);
        }
        committed = true;
        if (inputArguments.onCommitted !== null) {
            inputArguments.onCommitted();
        }
        await dependencies.renderCurrentConversation();
    } catch (error) {
        if (committed) {
            await dependencies.loadConversationMessages(inputArguments.conversationId, { force: true });
            dependencies.invalidateChatMarkup('both');
            await dependencies.refreshConversationsUI();
            throw error;
        }
        restoreConversationMutationSnapshot(conversation, mutationSnapshot);
        await dependencies.renderCurrentConversation();
        throw error;
    }
    requireNoActiveConversationExecution({ conversationId: inputArguments.conversationId, isConversationExecuting: (candidateConversationId) => dependencies.isConversationExecuting(candidateConversationId), context: 'Chat message edit' });
    await dependencies.streamResponse(conversation, {
        reportRequestFailure: false,
        skipInitialMessageSync: true
    });
};

const commitChatMessageResubmission = async (dependencies: ChatMessageEditCommitDependencies, inputArguments: { messageId: string; updatedText: string | null; removedAttachmentIndexes: readonly number[]; onCommitted: (() => void) | null }): Promise<void> => {
    const conversation = dependencies.getCurrentConversation();
    if (!conversation) {
        return;
    }
    const conversationId = requireConversationId(conversation.id, 'Conversation');

    await dependencies.runConversationExecutionIfIdle(conversationId, async () => {
        await commitChatMessageResubmissionInConversation(dependencies, {
            conversation,
            conversationId,
            messageId: inputArguments.messageId,
            updatedText: inputArguments.updatedText,
            removedAttachmentIndexes: inputArguments.removedAttachmentIndexes,
            onCommitted: inputArguments.onCommitted
        });
    });
};

const commitChatMessageEdit = async (dependencies: ChatMessageEditCommitDependencies, inputArguments: { messageId: string; updatedText: string; removedAttachmentIndexes: readonly number[]; onCommitted: () => void }): Promise<void> => {
    await commitChatMessageResubmission(dependencies, { messageId: inputArguments.messageId, updatedText: inputArguments.updatedText, removedAttachmentIndexes: inputArguments.removedAttachmentIndexes, onCommitted: inputArguments.onCommitted });
};

const commitChatMessageResend = async (dependencies: ChatMessageEditCommitDependencies, inputArguments: { messageId: string }): Promise<void> => {
    await commitChatMessageResubmission(dependencies, { messageId: inputArguments.messageId, updatedText: null, removedAttachmentIndexes: [], onCommitted: null });
};

export { commitChatMessageEdit, commitChatMessageResend };
export type { ChatMessageEditCommitDependencies };
