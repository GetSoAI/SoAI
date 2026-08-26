/* SoAI - Active chat stream follower disposal coordination [frontend/assets/ts/features/chat/chatstreamservice/activeStatusFollowerDisposal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatStreamNotificationRequestClearer } from '@features/chat/chatstreamservice/streamNotificationQueue.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

type ActiveStatusFollowerRetainedTimeline = {
    clearRequest(conversationId: string, requestId: string): void;
};

type ActiveStatusFollowerSessions = {
    disposeFollowerRequest(conversationId: string, requestId: string): void;
};

type ActiveStatusFollowerDisposalArguments = {
    sessions: Map<string, ChatStreamSession>;
    notificationQueue: ChatStreamNotificationRequestClearer;
    retainedToolTimeline: ActiveStatusFollowerRetainedTimeline;
    followerSessions: ActiveStatusFollowerSessions;
};

const disposeFollowerSession = (inputArguments: ActiveStatusFollowerDisposalArguments, conversationId: string, requestId: string): void => {
    inputArguments.notificationQueue.clearRequest(conversationId, requestId);
    inputArguments.retainedToolTimeline.clearRequest(conversationId, requestId);
    inputArguments.followerSessions.disposeFollowerRequest(conversationId, requestId);
    const currentSession = inputArguments.sessions.get(conversationId);
    if (currentSession && currentSession.transportMode === 'follower' && currentSession.requestId === requestId) {
        inputArguments.sessions.delete(conversationId);
    }
};

const deactivateFollowerSession = (inputArguments: ActiveStatusFollowerDisposalArguments, conversationId: string, session: ChatStreamSession): void => {
    session.active = false;
    disposeFollowerSession(inputArguments, conversationId, session.requestId);
};

export { deactivateFollowerSession };
