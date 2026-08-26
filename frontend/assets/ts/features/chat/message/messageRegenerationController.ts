/* SoAI - Assistant message regeneration transaction controller [frontend/assets/ts/features/chat/message/messageRegenerationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isObject } from '@core/typeGuards.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import { resolvePendingContentPreviewFeedback } from '@features/chat/contentPreviewFeedbackState.ts';
import { isChatMessage } from '@features/chat/message/chatMessageGuards.ts';
import { ChatExecutionModelPreflightBlockedError, applyPrimaryChatExecutionModelToConversation, requireChatExecutionModelPreflight, showChatExecutionModelPreflightBlockedError } from '@features/chat/modelExecutionPreflight.ts';
import { captureConversationMutationSnapshot, restoreConversationMutationSnapshot } from '@features/chat/execution/conversationMutationSnapshot.ts';
import { ChatStreamTerminalizationError, reportChatStreamTerminalizationFailureOnce } from '@features/chat/chatstreamservice/controller/terminalizationError.ts';
import { resolvePreviewContractFeedbackForStreamStart } from '@features/chat/chatstreamservice/controller/streamStartPreparation.ts';
import type { ChatMessageMutationDependencies } from '@features/chat/message/messageMutationControllerContracts.ts';
import { resolvePersistedMessageCursor } from '@features/chat/message/persistedMessageIdentity.ts';
import { requireConversationId } from '@features/chat/validation/ids.ts';

interface ChatMessageRegenerationDependencies extends ChatMessageMutationDependencies {
    truncateMessagesFromCursor: (conversation: ConversationContract, inputArguments: { createdAtMs: number; messageId: number }) => Promise<void>;
}

const isServerWindowedConversation = (conversation: ConversationContract): boolean => {
    return conversation.history !== undefined;
};

class ChatMessageRegenerationController {
    readonly #dependencies: ChatMessageRegenerationDependencies;

    constructor(dependencies: ChatMessageRegenerationDependencies) {
        this.#dependencies = dependencies;
    }

    async regenerateMessage(messageIndex: number): Promise<void> {
        try {
            await this.#dependencies.runWithBoundary('chat:regenerateMessage', async () => {
                const conversation = this.#dependencies.getCurrentConversation();
                if (!conversation) {
                    return;
                }
                const conversationId = requireConversationId(conversation.id, 'Conversation');
                const executionResult = await this.#dependencies.runConversationExecutionIfIdle(conversationId, async () => {
                    let modelPreflight: ReturnType<typeof requireChatExecutionModelPreflight>;
                    try {
                        modelPreflight = requireChatExecutionModelPreflight({
                            conversation,
                            selectedModelId: this.#dependencies.getCurrentModel(),
                            modelStreamHasPayload: this.#dependencies.getModelStreamHasPayload(),
                            isModelAvailable: (modelId) => this.#dependencies.isModelAvailable(modelId)
                        });
                    } catch (error) {
                        if (error instanceof ChatExecutionModelPreflightBlockedError) {
                            showChatExecutionModelPreflightBlockedError(error.reason);
                            return;
                        }
                        throw error;
                    }
                    if (messageIndex < 0 || messageIndex >= conversation.messages.length) {
                        return;
                    }
                    const mutationSnapshot = captureConversationMutationSnapshot(conversation);
                    let truncatePersisted = false;
                    let streamStarted = false;
                    let targetedMutationUsed = false;
                    try {
                        applyPrimaryChatExecutionModelToConversation(conversation, modelPreflight.primaryModelId);
                        const regenerationTarget = isObject(conversation.messages[messageIndex]) ? conversation.messages[messageIndex] : null;
                        const regenerationTargetMessage = regenerationTarget && isChatMessage(regenerationTarget) ? regenerationTarget : null;
                        const cursor = regenerationTargetMessage && isServerWindowedConversation(conversation) ? resolvePersistedMessageCursor(regenerationTargetMessage) : null;
                        if (isServerWindowedConversation(conversation) && cursor === null) {
                            throw new Error('Persisted regeneration target cursor is missing.');
                        }
                        const contentPreviewFeedback = regenerationTargetMessage ? resolvePendingContentPreviewFeedback(regenerationTargetMessage) : null;
                        const previewContractFeedback = resolvePreviewContractFeedbackForStreamStart(regenerationTargetMessage, {});

                        conversation.messages = conversation.messages.slice(0, messageIndex);
                        try {
                            if (cursor === null) {
                                await this.#dependencies.saveAndSync(conversation);
                            } else {
                                targetedMutationUsed = true;
                                await this.#dependencies.truncateMessagesFromCursor(conversation, {
                                    createdAtMs: cursor.createdAtMs,
                                    messageId: cursor.id
                                });
                            }
                            truncatePersisted = true;
                        } catch (error) {
                            restoreConversationMutationSnapshot(conversation, mutationSnapshot);
                            await this.#dependencies.loadConversationMessages(conversationId, { force: true });
                            this.#dependencies.invalidateChatMarkup('both');
                            await this.#dependencies.refreshConversationsUI();
                            throw error;
                        }
                        this.#dependencies.invalidateChatMarkup('current');
                        await this.#dependencies.renderCurrentConversation();
                        streamStarted = true;
                        await this.#dependencies.streamResponse(conversation, {
                            contentPreviewFeedback,
                            contentPreviewFeedbackSourceMessage: regenerationTargetMessage,
                            previewContractFeedback,
                            reportRequestFailure: false,
                            skipInitialMessageSync: true
                        });
                    } catch (error) {
                        if (error instanceof ChatStreamTerminalizationError) {
                            throw error;
                        }
                        if (streamStarted) {
                            await this.#dependencies.loadConversationMessages(conversationId, { force: true });
                            this.#dependencies.invalidateChatMarkup('both');
                            await this.#dependencies.refreshConversationsUI();
                            throw error;
                        }
                        if (truncatePersisted) {
                            await this.#restoreCommittedRegenerationMutation(conversation, mutationSnapshot, conversationId, targetedMutationUsed);
                        }
                        if (error instanceof ChatExecutionModelPreflightBlockedError) {
                            showChatExecutionModelPreflightBlockedError(error.reason);
                            return;
                        }
                        throw error;
                    }
                });
                if (executionResult.status === 'busy') {
                    return;
                }
            });
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!reportChatStreamTerminalizationFailureOnce(runtimeError, (failure) => this.#dependencies.reportRequestFailure(failure))) {
                this.#dependencies.reportRequestFailure(runtimeError);
            }
        }
    }

    async #restoreCommittedRegenerationMutation(conversation: ConversationContract, mutationSnapshot: ReturnType<typeof captureConversationMutationSnapshot>, conversationId: string, targetedMutationUsed: boolean): Promise<void> {
        restoreConversationMutationSnapshot(conversation, mutationSnapshot);
        if (targetedMutationUsed) {
            await this.#dependencies.loadConversationMessages(conversationId, { force: true });
            this.#dependencies.invalidateChatMarkup('both');
            await this.#dependencies.refreshConversationsUI();
            return;
        }
        try {
            await this.#dependencies.saveAndSync(conversation);
        } catch (error) {
            await this.#dependencies.loadConversationMessages(conversationId, { force: true });
            this.#dependencies.invalidateChatMarkup('both');
            await this.#dependencies.refreshConversationsUI();
            throw error;
        }
        this.#dependencies.invalidateChatMarkup('both');
        await this.#dependencies.refreshConversationsUI();
    }
}

export { ChatMessageRegenerationController, type ChatMessageRegenerationDependencies };
