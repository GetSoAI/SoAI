/* SoAI - Chat stream service disposal coordination [frontend/assets/ts/features/chat/chatstreamservice/serviceDisposal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatStreamOwnerDispatch } from '@features/chat/chatstreamservice/ownerDispatch.ts';
import type { PendingStopRequest } from '@features/chat/chatstreamservice/pendingStopRequests.ts';
import type { RetainedToolTimelineCoordinator } from '@features/chat/chatstreamservice/retainedToolTimelineCoordinator.ts';
import type { StreamRequestDispositionRegistry } from '@features/chat/chatstreamservice/streamRequestDispositionRegistry.ts';
import { resetChatStreamSessions } from '@features/chat/chatstreamservice/sessionReset.ts';
import type { ChatStreamConversationTitleResolution } from '@features/chat/chatstreamservice/conversationTitleResolution.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

const disposeChatStreamServiceState = (inputArguments: { sessions: Map<string, ChatStreamSession>; retainedToolTimeline: RetainedToolTimelineCoordinator; pendingStopRequests: Map<string, PendingStopRequest>; requestDispositions: StreamRequestDispositionRegistry; ownerDispatch: ChatStreamOwnerDispatch; conversationTitles: ChatStreamConversationTitleResolution }): void => {
    resetChatStreamSessions({
        sessions: inputArguments.sessions,
        retainedToolTimeline: inputArguments.retainedToolTimeline
    });
    inputArguments.retainedToolTimeline.dispose();
    inputArguments.pendingStopRequests.clear();
    inputArguments.requestDispositions.clearAll();
    inputArguments.ownerDispatch.clear();
    inputArguments.conversationTitles.clear();
};

export { disposeChatStreamServiceState };
