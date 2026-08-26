/* SoAI - Chat send guard evaluation controller [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/sendFlowGuardController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveSendLockKey } from '@pages/chat/controllers/chatmessagesendingcontroller/ConversationSendLockManager.ts';
import { QUEUED_SEND_SENT, blockQueuedSend } from '@pages/chat/controllers/chatmessagesendingcontroller/constants.ts';
import type { ChatStreamingController, QueuedSendBlockReason, QueuedSendGuard, QueuedSendGuardResult, QueuedSendOutcome } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

const normalizeGuardBlockReason = (result: QueuedSendGuardResult | undefined): QueuedSendBlockReason | null => {
    if (result === undefined || result === true) {
        return null;
    }
    if (result === false) {
        return 'stale';
    }
    return result.reason;
};

const runQueuedSendGuard = (inputArguments: { beforeSend: QueuedSendGuard | null | undefined; conversationId: string; initialSendLockKey: string; createdConversationForSend: boolean; isFirstMessage: boolean; chatStreamingController: ChatStreamingController }): QueuedSendOutcome => {
    const guardResult = inputArguments.beforeSend?.({
        conversationId: inputArguments.conversationId,
        startedFromEmptyConversation: inputArguments.initialSendLockKey === resolveSendLockKey(null),
        createdConversationForSend: inputArguments.createdConversationForSend,
        isFirstMessage: inputArguments.isFirstMessage,
        isStreaming: inputArguments.chatStreamingController.isStreamingConversation(inputArguments.conversationId)
    });
    const blockReason = normalizeGuardBlockReason(guardResult);
    return blockReason === null ? QUEUED_SEND_SENT : blockQueuedSend(blockReason);
};

export { runQueuedSendGuard };
