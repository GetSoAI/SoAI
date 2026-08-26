/* SoAI - Chat feature stop streaming [frontend/assets/ts/features/chat/chatstreamservice/controller/actions/stopStreaming.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatStreamingControllerContext } from '@features/chat/chatstreamservice/controller/types.ts';
import { cancelActiveStreamForConversation, resolveCurrentStreamCancellationConversationId } from '@features/chat/chatstreamservice/controller/actions/streamCancellation.ts';
import type { ChatStreamStopOptions } from '@features/chat/chatstreamservice/types.ts';

export function stopStreaming(context: ChatStreamingControllerContext, options: ChatStreamStopOptions = {}): void {
    const conversationId = resolveCurrentStreamCancellationConversationId(context);
    if (!conversationId) {
        return;
    }
    cancelActiveStreamForConversation(context, conversationId, options);
}
