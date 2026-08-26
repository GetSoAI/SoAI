/* SoAI - Chat stream authenticated session reset policy [frontend/assets/ts/features/chat/chatstreamservice/sessionReset.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RetainedToolTimelineCoordinator } from '@features/chat/chatstreamservice/retainedToolTimelineCoordinator.ts';
import { markChatStreamOwnerReleaseRequested } from '@features/chat/chatstreamservice/streamOwnerRelease.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

const resetChatStreamSessions = (inputArguments: { sessions: Map<string, ChatStreamSession>; retainedToolTimeline: RetainedToolTimelineCoordinator }): void => {
    for (const [conversationId, session] of inputArguments.sessions.entries()) {
        inputArguments.retainedToolTimeline.clearConversation(conversationId);
        if (session.active) {
            markChatStreamOwnerReleaseRequested(session);
            session.abortController.abort();
        }
        session.active = false;
    }
    inputArguments.sessions.clear();
};

export { resetChatStreamSessions };
