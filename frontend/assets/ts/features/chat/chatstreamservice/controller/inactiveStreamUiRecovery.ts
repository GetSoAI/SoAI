/* SoAI - Inactive stream UI recovery [frontend/assets/ts/features/chat/chatstreamservice/controller/inactiveStreamUiRecovery.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { getConversationStreamState, reconcileInactiveSyncedConversation } from '@features/chat/chatstreamservice/controller/state.ts';
import { renderCurrentConversationSafely } from '@features/chat/chatstreamservice/controller/renderScheduling.ts';
import type { ChatStreamingControllerContext, ConversationStreamState } from '@features/chat/chatstreamservice/controller/types.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const isRecoverableInactiveStreamingState = (context: ChatStreamingControllerContext, conversationId: string, expectedState: ConversationStreamState): boolean => {
    const currentState = getConversationStreamState(context, conversationId);
    return !context.disposed && context.presentationActive && currentState === expectedState && currentState.phase === 'streaming' && currentState.terminalRenderTimerId === null && currentState.terminalizationPromise === null && !context.dependencies.chatStreamService.isStreaming(conversationId);
};

const recoverInactiveStreamingUi = async (context: ChatStreamingControllerContext, conversationId: string, expectedState: ConversationStreamState): Promise<void> => {
    const presentationGeneration = context.presentationGeneration;
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId || !isRecoverableInactiveStreamingState(context, normalizedConversationId, expectedState)) {
        return;
    }
    try {
        await context.dependencies.storageManager.loadConversationMessages(normalizedConversationId, {
            force: true,
            mergeStreamingAssistants: false
        });
    } catch (error) {
        context.errorHandler?.debug?.('ChatStream', `Failed to hydrate an inactive stream before UI recovery for ${normalizedConversationId}`, ensureError(error));
    }
    if (context.presentationGeneration !== presentationGeneration || !isRecoverableInactiveStreamingState(context, normalizedConversationId, expectedState)) {
        return;
    }
    reconcileInactiveSyncedConversation(context, normalizedConversationId);
    if (normalizeConversationId(context.dependencies.state.getCurrentConversationId()) !== normalizedConversationId) {
        return;
    }
    context.dependencies.presentation.invalidateChatMarkup('current');
    await renderCurrentConversationSafely(context, `Failed to render the recovered inactive stream for ${normalizedConversationId}`);
};

export { recoverInactiveStreamingUi };
