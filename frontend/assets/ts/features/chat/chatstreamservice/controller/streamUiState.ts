/* SoAI - Chat stream controller UI state transition coordination [frontend/assets/ts/features/chat/chatstreamservice/controller/streamUiState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scheduleConversationListRender } from '@features/chat/chatstreamservice/controller/renderScheduling.ts';
import type { ChatStreamingControllerContext } from '@features/chat/chatstreamservice/controller/types.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const syncCurrentConversationStreamingControls = (context: ChatStreamingControllerContext): void => {
    if (context.disposed) {
        return;
    }
    context.dependencies.uiManager.applyExecutionControls();
};

const applyStreamingUiTransition = (
    context: ChatStreamingControllerContext,
    inputArguments: {
        conversationId: string;
        previousIsStreaming: boolean;
        nextIsStreaming: boolean;
        listRenderReason: string;
    }
): void => {
    if (context.disposed) {
        return;
    }
    const conversationId = normalizeConversationId(inputArguments.conversationId);
    if (!conversationId) {
        return;
    }
    syncCurrentConversationStreamingControls(context);
    if (inputArguments.previousIsStreaming === inputArguments.nextIsStreaming) {
        return;
    }
    context.dependencies.onStreamingStateChange?.(conversationId, inputArguments.nextIsStreaming);
    scheduleConversationListRender(context, inputArguments.listRenderReason);
};

export { applyStreamingUiTransition, syncCurrentConversationStreamingControls };
