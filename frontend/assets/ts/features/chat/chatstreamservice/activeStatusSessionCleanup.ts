/* SoAI - Active chat stream session cleanup policy [frontend/assets/ts/features/chat/chatstreamservice/activeStatusSessionCleanup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ActiveChatStreamStatus } from '@features/chat/chatstreamservice/activeStreamStatus.ts';
import { deactivateFollowerSession } from '@features/chat/chatstreamservice/activeStatusFollowerDisposal.ts';
import { sessionMatchesActiveStatus } from '@features/chat/chatstreamservice/activeStatusSessionState.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import type { ChatStreamNotificationRequestClearer } from '@features/chat/chatstreamservice/streamNotificationQueue.ts';
import { chatStreamIdentityPrecedesSession, sessionPrecedesChatStreamIdentity, type ChatStreamMessageOrderIdentity } from '@features/chat/chatstreamservice/streamIdentity.ts';
import { finalizeChatStreamOwnerCancellation } from '@features/chat/chatstreamservice/streamTerminalizationPolicy.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

type ActiveStatusCleanupArguments = {
    sessions: Map<string, ChatStreamSession>;
    runtime: StreamRuntime;
    notificationQueue: ChatStreamNotificationRequestClearer;
    retainedToolTimeline: {
        clearRequest(conversationId: string, requestId: string): void;
    };
    followerSessions: {
        disposeFollowerRequest(conversationId: string, requestId: string): void;
    };
    ownerDispatch: {
        unregisterConversation(conversationId: string, requestId: string): void;
    };
};

const sessionPrecedesActiveStatus = (session: ChatStreamSession, status: ActiveChatStreamStatus): boolean => {
    return sessionPrecedesChatStreamIdentity(session, status);
};

const activeStatusPrecedesSession = (identity: ChatStreamMessageOrderIdentity, session: ChatStreamSession): boolean => {
    return chatStreamIdentityPrecedesSession(identity, session);
};

const discardOwnerSession = (inputArguments: ActiveStatusCleanupArguments, conversationId: string, session: ChatStreamSession): void => {
    session.active = false;
    inputArguments.ownerDispatch.unregisterConversation(conversationId, session.requestId);
    inputArguments.notificationQueue.clearRequest(conversationId, session.requestId);
    inputArguments.retainedToolTimeline.clearRequest(conversationId, session.requestId);
    session.abortController.abort();
    if (inputArguments.sessions.get(conversationId) === session) {
        inputArguments.sessions.delete(conversationId);
    }
};

const releaseStaleOwnerSession = (inputArguments: ActiveStatusCleanupArguments, conversationId: string, session: ChatStreamSession): void => {
    finalizeChatStreamOwnerCancellation({
        session,
        runtime: inputArguments.runtime,
        notifyUser: false
    });
    discardOwnerSession(inputArguments, conversationId, session);
};

const handleIgnoredActiveStatus = (inputArguments: ActiveStatusCleanupArguments, status: ActiveChatStreamStatus): void => {
    const session = inputArguments.sessions.get(status.conversationId);
    if (!session || !session.active) {
        return;
    }
    if (session.transportMode === 'owner') {
        if (sessionPrecedesActiveStatus(session, status)) {
            releaseStaleOwnerSession(inputArguments, status.conversationId, session);
        }
        return;
    }
    if (sessionMatchesActiveStatus(session, status) || sessionPrecedesActiveStatus(session, status)) {
        deactivateFollowerSession(inputArguments, status.conversationId, session);
    }
};

export { activeStatusPrecedesSession, discardOwnerSession, handleIgnoredActiveStatus, releaseStaleOwnerSession };
