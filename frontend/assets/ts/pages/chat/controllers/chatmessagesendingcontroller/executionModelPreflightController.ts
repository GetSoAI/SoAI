/* SoAI - Chat send execution model preflight [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/executionModelPreflightController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ChatExecutionModelPreflightBlockedError, preflightChatExecutionModelSelection, requireChatExecutionModelPreflight, showChatExecutionModelPreflightBlockedError, type Conversation } from '@features/chat/public.ts';
import { blockQueuedSend } from '@pages/chat/controllers/chatmessagesendingcontroller/constants.ts';
import type { MessageSendingHost, QueuedSendOutcome } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

type ChatExecutionModelPreflight = ReturnType<typeof requireChatExecutionModelPreflight>;
type SendExecutionModelPreflightResult = { status: 'ok'; plan: ChatExecutionModelPreflight } | { status: 'blocked'; outcome: QueuedSendOutcome };

const resolveSelectedModelPreflight = (host: MessageSendingHost, selectedModelId: string | null): QueuedSendOutcome | null => {
    const preflight = preflightChatExecutionModelSelection({
        selectedModelId,
        modelStreamHasPayload: host.model.getModelStreamHasPayload(),
        isModelAvailable: (candidateModelId) => host.model.isModelAvailable(candidateModelId)
    });
    if (preflight.status === 'ok') {
        return null;
    }
    showChatExecutionModelPreflightBlockedError(preflight.reason);
    return blockQueuedSend('stale');
};

const resolveSendExecutionModelPreflight = (host: MessageSendingHost, conversation: Conversation): SendExecutionModelPreflightResult => {
    try {
        const plan = requireChatExecutionModelPreflight({
            conversation,
            selectedModelId: host.model.getCurrentModel(),
            modelStreamHasPayload: host.model.getModelStreamHasPayload(),
            isModelAvailable: (candidateModelId) => host.model.isModelAvailable(candidateModelId)
        });
        return { status: 'ok', plan };
    } catch (error) {
        if (error instanceof ChatExecutionModelPreflightBlockedError) {
            showChatExecutionModelPreflightBlockedError(error.reason);
            return { status: 'blocked', outcome: blockQueuedSend('stale') };
        }
        throw error;
    }
};

export { resolveSelectedModelPreflight, resolveSendExecutionModelPreflight };
export type { ChatExecutionModelPreflight };
