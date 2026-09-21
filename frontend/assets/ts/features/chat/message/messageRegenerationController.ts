/* SoAI - Assistant message regeneration admission controller [frontend/assets/ts/features/chat/message/messageRegenerationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isObject } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolvePreviewContractFeedbackForStreamStart } from '@features/chat/chatstreamservice/controller/streamStartPreparation.ts';
import { serializeContentPreviewFeedback, serializePreviewContractFeedback } from '@features/chat/chatstreamservice/streamStartPayload.ts';
import { markContentPreviewFeedbackDelivered, resolvePendingContentPreviewFeedback } from '@features/chat/contentPreviewFeedbackState.ts';
import { isChatConversationSettingsWritable } from '@features/chat/conversation/conversationSettingsEligibility.ts';
import { isChatMessage } from '@features/chat/message/chatMessageGuards.ts';
import type { ChatMessageMutationDependencies } from '@features/chat/message/messageMutationControllerContracts.ts';
import { resolvePersistedMessageCursor } from '@features/chat/message/persistedMessageIdentity.ts';
import { ChatExecutionModelPreflightBlockedError, normalizeChatExecutionModelId, requireChatExecutionModelPreflight, showChatExecutionModelPreflightBlockedError } from '@features/chat/modelExecutionPreflight.ts';
import { requireConversationId } from '@features/chat/validation/ids.ts';

interface ChatMessageRegenerationDependencies extends ChatMessageMutationDependencies {
    regenerateConversation: (conversationId: string, payload: { expectedLastModifiedAtMs: number; target: { createdAtMs: number; messageId: number }; contentPreviewFeedback: JsonObject | null; previewContractFeedback: JsonObject | null }) => Promise<void>;
    updateConversationModel: (conversationId: string, modelId: string) => Promise<void>;
}

class ChatMessageRegenerationController {
    readonly #dependencies: ChatMessageRegenerationDependencies;

    constructor(dependencies: ChatMessageRegenerationDependencies) {
        this.#dependencies = dependencies;
    }

    async regenerateMessage(messageIndex: number): Promise<void> {
        try {
            await this.#dependencies.runWithBoundary('chat:regenerateMessage', async () => {
                const conversation = this.#dependencies.getCurrentConversation();
                if (!conversation || messageIndex < 0 || messageIndex >= conversation.messages.length) return;
                const conversationId = requireConversationId(conversation.id, 'Conversation');
                const targetValue = conversation.messages[messageIndex];
                const target = isObject(targetValue) && isChatMessage(targetValue) ? targetValue : null;
                const cursor = target === null ? null : resolvePersistedMessageCursor(target);
                if (target === null || cursor === null || conversation.history === undefined) {
                    throw new Error('Persisted regeneration target cursor is missing.');
                }
                const executionResult = await this.#dependencies.runConversationExecutionIfIdle(conversationId, async () => {
                    const activeTarget = this.#resolveActiveTarget(conversationId, cursor.createdAtMs, cursor.id);
                    const activeConversation = this.#dependencies.getCurrentConversation();
                    if (activeTarget === null || activeConversation === null) return;
                    const contentPreviewFeedback = resolvePendingContentPreviewFeedback(activeTarget);
                    const previewContractFeedback = resolvePreviewContractFeedbackForStreamStart(activeTarget, {});
                    let primaryModelId: string | null = null;
                    try {
                        primaryModelId = requireChatExecutionModelPreflight({
                            conversation: activeConversation,
                            selectedModelId: this.#dependencies.getCurrentModel(),
                            modelStreamHasPayload: this.#dependencies.getModelStreamHasPayload(),
                            isModelAvailable: (modelId) => this.#dependencies.isModelAvailable(modelId)
                        }).primaryModelId;
                    } catch (error) {
                        if (error instanceof ChatExecutionModelPreflightBlockedError) {
                            showChatExecutionModelPreflightBlockedError(error.reason);
                            return;
                        }
                        throw error;
                    }
                    if (primaryModelId === null) return;
                    if (isChatConversationSettingsWritable(activeConversation) && normalizeChatExecutionModelId(activeConversation.modelSettings?.model) !== primaryModelId) {
                        await this.#dependencies.updateConversationModel(conversationId, primaryModelId);
                    }
                    if (!this.#isTargetStillActive(conversationId, cursor.createdAtMs, cursor.id)) return;
                    const authoritativeConversation = this.#dependencies.getCurrentConversation();
                    const expectedRevision = authoritativeConversation?.updatedAt;
                    if (!authoritativeConversation || authoritativeConversation.id !== conversationId || !Number.isInteger(expectedRevision) || Number(expectedRevision) <= 0) {
                        throw new Error('Conversation regeneration revision is missing.');
                    }
                    await this.#dependencies.regenerateConversation(conversationId, {
                        expectedLastModifiedAtMs: Number(expectedRevision),
                        target: { createdAtMs: cursor.createdAtMs, messageId: cursor.id },
                        contentPreviewFeedback: contentPreviewFeedback === null ? null : serializeContentPreviewFeedback(contentPreviewFeedback),
                        previewContractFeedback: previewContractFeedback === null ? null : serializePreviewContractFeedback(previewContractFeedback)
                    });
                    markContentPreviewFeedbackDelivered(activeTarget);
                    if (!this.#isTargetStillActive(conversationId, cursor.createdAtMs, cursor.id)) return;
                    await this.#dependencies.loadConversationMessages(conversationId, { force: true });
                    if (this.#dependencies.getCurrentConversation()?.id !== conversationId) return;
                    this.#dependencies.invalidateChatMarkup('both');
                    await this.#dependencies.refreshConversationsUI();
                });
                if (executionResult.status === 'busy') return;
            });
        } catch (error) {
            this.#dependencies.reportRequestFailure(ensureError(error));
        }
    }

    #resolveActiveTarget(conversationId: string, createdAtMs: number, messageId: number): ChatMessage | null {
        const activeConversation = this.#dependencies.getCurrentConversation();
        if (!activeConversation || activeConversation.id !== conversationId) return null;
        return (
            activeConversation.messages.find((message) => {
                const cursor = isChatMessage(message) ? resolvePersistedMessageCursor(message) : null;
                return cursor?.createdAtMs === createdAtMs && cursor.id === messageId;
            }) ?? null
        );
    }

    #isTargetStillActive(conversationId: string, createdAtMs: number, messageId: number): boolean {
        return this.#resolveActiveTarget(conversationId, createdAtMs, messageId) !== null;
    }
}

export { ChatMessageRegenerationController };
export type { ChatMessageRegenerationDependencies };
