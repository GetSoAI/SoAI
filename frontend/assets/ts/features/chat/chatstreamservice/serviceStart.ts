/* SoAI - Chat stream owner start coordination [frontend/assets/ts/features/chat/chatstreamservice/serviceStart.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { registerAbortListener } from '@features/chat/abort/abortSignalListener.ts';
import type { ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import { createOwnerChatStreamSession } from '@features/chat/chatstreamservice/ownerSessionFactory.ts';
import type { ChatStreamOwnerDispatch } from '@features/chat/chatstreamservice/ownerDispatch.ts';
import type { PendingStopRequest } from '@features/chat/chatstreamservice/pendingStopRequests.ts';
import { resolveStopRequest } from '@features/chat/chatstreamservice/serviceStop.ts';
import { runStreamSession } from '@features/chat/chatstreamservice/streamRunSession.ts';
import { requireChatStreamIdentityFromStartArguments } from '@features/chat/chatstreamservice/streamIdentity.ts';
import type { StreamRequestDispositionRegistry } from '@features/chat/chatstreamservice/streamRequestDispositionRegistry.ts';
import type { RetainedToolTimelineCoordinator } from '@features/chat/chatstreamservice/retainedToolTimelineCoordinator.ts';
import type { ChatStreamNotificationRequestClearer } from '@features/chat/chatstreamservice/streamNotificationQueue.ts';
import type { ChatStreamSession, ChatStreamSessionMeta, ChatStreamStartOptions, ChatStreamStartOutcome } from '@features/chat/chatstreamservice/types.ts';

type StartChatStreamFollowerSessions = {
    disposeFollowerConversation(conversationId: string): void;
    syncActiveStatusReconciliation(): void;
};

type StartChatStreamSessionArguments = {
    apiClient: ChatStreamApiClient;
    sessions: Map<string, ChatStreamSession>;
    pendingStopRequests: Map<string, PendingStopRequest>;
    requestDispositions: StreamRequestDispositionRegistry;
    ownerDispatch: ChatStreamOwnerDispatch;
    notificationQueue: ChatStreamNotificationRequestClearer;
    retainedToolTimeline: RetainedToolTimelineCoordinator;
    followerSessions: StartChatStreamFollowerSessions;
    runtime: StreamRuntime;
    options: ChatStreamStartOptions;
    admissionState: {
        markInactive(conversationId: string): void;
    };
    isCurrent(): boolean;
    syncActiveStatusAfterOwnerRelease(conversationId: string): Promise<void>;
};

const startChatStreamSession = async (inputArguments: StartChatStreamSessionArguments): Promise<ChatStreamStartOutcome> => {
    const options = inputArguments.options;
    const identity = requireChatStreamIdentityFromStartArguments({
        conversationId: options.conversationId,
        requestId: options.requestId,
        assistantTimestamp: options.assistantTimestamp,
        assistantTurnTimestamp: options.assistantTurnTimestamp,
        modelVariantIndex: options.modelVariantIndex
    });
    if (!toTrimmedString(options.conversationTitle)) {
        throw new Error('Chat stream start requires a valid conversationTitle');
    }
    const nowMs = monotonicMs();

    const activeSession = inputArguments.sessions.get(identity.convId);
    if (activeSession && activeSession.active) {
        if (activeSession.requestId === identity.requestId) {
            await activeSession.promise;
            return activeSession.status;
        }
        if (activeSession.status === 'streaming' && !inputArguments.requestDispositions.isRequestSuppressed(activeSession.conversationId, activeSession.requestId)) {
            throw new Error(`Chat stream already active for conversation ${identity.convId}`);
        }
        activeSession.active = false;
        activeSession.abortController.abort();
        inputArguments.ownerDispatch.unregisterConversation(identity.convId, activeSession.requestId);
        inputArguments.notificationQueue.clearRequest(identity.convId, activeSession.requestId);
        inputArguments.retainedToolTimeline.clearRequest(identity.convId, activeSession.requestId);
        if (activeSession.transportMode === 'follower') {
            inputArguments.followerSessions.disposeFollowerConversation(identity.convId);
        }
        inputArguments.sessions.delete(identity.convId);
        inputArguments.followerSessions.syncActiveStatusReconciliation();
    }

    const pendingStop = resolveStopRequest(inputArguments.pendingStopRequests, identity.convId, identity.requestId, nowMs);
    const meta: ChatStreamSessionMeta = {
        conversationId: identity.convId,
        conversationTitle: options.conversationTitle,
        model: options.model,
        assistantTimestamp: identity.assistantTimestamp,
        assistantTurnTimestamp: identity.assistantTurnTimestamp,
        modelVariantIndex: identity.modelVariantIndex,
        requestId: identity.requestId
    };
    const abortController = new AbortController();
    const externalAbortSignal = options.abortSignal ?? null;
    let unregisterExternalAbortListener: (() => void) | null = null;
    if (externalAbortSignal?.aborted) {
        abortController.abort();
    } else if (externalAbortSignal !== null) {
        unregisterExternalAbortListener = registerAbortListener(externalAbortSignal, () => abortController.abort());
    }
    const session = createOwnerChatStreamSession({
        meta,
        abortController,
        onFirstServerEvent: options.onFirstServerEvent
    });
    inputArguments.sessions.set(identity.convId, session);
    if (pendingStop) {
        session.pendingCancellation = { reason: pendingStop.reason, forcePendingSteers: pendingStop.forcePendingSteers };
        abortController.abort();
    }

    session.promise = runStreamSession(
        session,
        options.requestBody,
        options.contentPreviewFeedback ?? null,
        options.previewContractFeedback ?? null,
        inputArguments.runtime,
        ({ conversationId: convId, requestId: requestId, handleStreamEvent, handleCommandErrorEvent, applyHydratedSnapshot }) => {
            return inputArguments.ownerDispatch.register({
                conversationId: convId,
                requestId: requestId,
                handleStreamEvent,
                handleCommandErrorEvent,
                applyHydratedSnapshot
            });
        },
        {
            apiClient: inputArguments.apiClient,
            syncActiveStatusAfterOwnerRelease: inputArguments.syncActiveStatusAfterOwnerRelease
        }
    ).finally(async () => {
        unregisterExternalAbortListener?.();
        unregisterExternalAbortListener = null;
        if (!inputArguments.isCurrent()) {
            return;
        }
        const detached = session.ownerReleaseRequested && session.status === 'streaming';
        if (!detached && !session.firstServerEventHandled) {
            inputArguments.requestDispositions.markFollowerQuarantine(identity.convId, identity.requestId);
        }
        if (!detached) inputArguments.requestDispositions.markTerminalObserved(identity.convId, identity.requestId);
        const currentSession = inputArguments.sessions.get(identity.convId);
        if (currentSession === session && !session.active) {
            if (session.status !== 'streaming') {
                inputArguments.admissionState.markInactive(identity.convId);
            }
            if (detached) inputArguments.retainedToolTimeline.clearRequest(identity.convId, identity.requestId);
            else await inputArguments.retainedToolTimeline.maybeRetainOwnerSessionAfterHydration(identity.convId, session);
            inputArguments.sessions.delete(identity.convId);
        }
        inputArguments.followerSessions.syncActiveStatusReconciliation();
    });
    inputArguments.followerSessions.syncActiveStatusReconciliation();
    await session.promise;
    return session.ownerReleaseRequested && session.status === 'streaming' ? 'detached' : session.status;
};

export { startChatStreamSession };
