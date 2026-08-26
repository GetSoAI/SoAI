/* SoAI - Active chat stream inactive transition reconciliation [frontend/assets/ts/features/chat/chatstreamservice/activeStatusInactiveTransition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { applyAssistantMessageSnapshot, sessionMatchesActiveStatus } from '@features/chat/chatstreamservice/activeStatusSessionState.ts';
import { deactivateFollowerSession } from '@features/chat/chatstreamservice/activeStatusFollowerDisposal.ts';
import { activeStatusPrecedesSession, discardOwnerSession } from '@features/chat/chatstreamservice/activeStatusSessionCleanup.ts';
import type { ChatStreamApiClient } from '@features/chat/chatstreamservice/chatStreamApi.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import type { ChatStreamStatusSnapshot } from '@features/chat/chatstreamservice/activeStreamStatus.ts';
import { waitForInactiveTerminalAssistantState } from '@features/chat/chatstreamservice/inactiveTerminalHydration.ts';
import { finalizeChatStreamHydratedTerminal, finalizeChatStreamProtocolFailure } from '@features/chat/chatstreamservice/streamTerminalizationPolicy.ts';
import { resolveHydratedTerminalStatus } from '@features/chat/chatstreamservice/streamHydratedTerminalStatus.ts';
import type { ChatStreamNotificationRequestClearer } from '@features/chat/chatstreamservice/streamNotificationQueue.ts';
import type { ChatStreamSession, HydratedSnapshotApplicationResult } from '@features/chat/chatstreamservice/types.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type InactiveTerminalStreamIdentity = {
    conversationId: string;
    assistantTimestamp: number;
    assistantTurnTimestamp: number;
    modelVariantIndex: number;
};

type InactiveTerminalizationResult = 'not-terminalized' | 'hydrated-terminal' | 'missing-terminal-snapshot' | 'suppressed';

type ActiveStatusInactiveTransitionRequestDispositions = {
    shouldIgnorePassiveStreamEvent(conversationId: string, requestId: string): boolean;
};

type ActiveStatusInactiveTransitionOwnerDispatch = {
    applySnapshot(conversationId: string, requestId: string, assistantMessage: ChatMessage, notifyUserOnTerminal: boolean): Promise<HydratedSnapshotApplicationResult | null>;
    unregisterConversation(conversationId: string, requestId: string): void;
};

type ActiveStatusInactiveTransitionArguments = {
    apiClient: ChatStreamApiClient;
    sessions: Map<string, ChatStreamSession>;
    runtime: StreamRuntime;
    retainedToolTimeline: {
        clearRequest(conversationId: string, requestId: string): void;
    };
    notificationQueue: ChatStreamNotificationRequestClearer;
    followerSessions: {
        disposeFollowerRequest(conversationId: string, requestId: string): void;
        applyFollowerSnapshot(conversationId: string, requestId: string, assistantMessage: ChatMessage, notifyUserOnTerminal: boolean): Promise<HydratedSnapshotApplicationResult | null>;
    };
    ownerDispatch: ActiveStatusInactiveTransitionOwnerDispatch;
    requestDispositions: ActiveStatusInactiveTransitionRequestDispositions;
    admissionState: {
        update(status: ChatStreamStatusSnapshot): void;
    };
    isCurrent: () => boolean;
    signal?: AbortSignal | undefined;
};

const INACTIVE_TERMINAL_STATE_MISSING_MESSAGE = 'Inactive chat stream status did not include terminal assistant stream state.';

const finalizeInactiveFollowerSession = (inputArguments: ActiveStatusInactiveTransitionArguments, session: ChatStreamSession): InactiveTerminalizationResult => {
    const terminalStatus = resolveHydratedTerminalStatus(session);
    if (terminalStatus === null) {
        finalizeChatStreamProtocolFailure({
            session,
            runtime: inputArguments.runtime,
            message: INACTIVE_TERMINAL_STATE_MISSING_MESSAGE,
            errorCode: 'protocol_error'
        });
        deactivateFollowerSession(inputArguments, session.conversationId, session);
        return 'missing-terminal-snapshot';
    }
    finalizeChatStreamHydratedTerminal({
        session,
        runtime: inputArguments.runtime,
        status: terminalStatus,
        finishReason: terminalStatus === 'complete' ? (session.assistantMessage.finishReason ?? null) : terminalStatus,
        notifyUser: false
    });
    deactivateFollowerSession(inputArguments, session.conversationId, session);
    return 'hydrated-terminal';
};

const shouldContinueInactiveTerminalPolling = (inputArguments: ActiveStatusInactiveTransitionArguments, identity: InactiveTerminalStreamIdentity, continueWhenSessionMissing: boolean): boolean => {
    if (!inputArguments.isCurrent()) {
        return false;
    }
    const currentSession = inputArguments.sessions.get(identity.conversationId);
    if (!currentSession || !currentSession.active) {
        return continueWhenSessionMissing;
    }
    return !activeStatusPrecedesSession(identity, currentSession);
};

const waitForInactiveTerminalSnapshot = async (inputArguments: ActiveStatusInactiveTransitionArguments, identity: InactiveTerminalStreamIdentity, initialMessage: ChatStreamSession['assistantMessage'], continueWhenSessionMissing: boolean): Promise<ChatStreamSession['assistantMessage'] | null> => {
    return await waitForInactiveTerminalAssistantState({
        apiClient: inputArguments.apiClient,
        identity: {
            conversationId: identity.conversationId,
            assistantTimestamp: identity.assistantTimestamp,
            assistantTurnTimestamp: identity.assistantTurnTimestamp,
            modelVariantIndex: identity.modelVariantIndex
        },
        initialMessage,
        signal: inputArguments.signal,
        shouldContinue: () => shouldContinueInactiveTerminalPolling(inputArguments, identity, continueWhenSessionMissing)
    });
};

const applyInactiveOwnerSnapshot = async (inputArguments: ActiveStatusInactiveTransitionArguments, session: ChatStreamSession, assistantMessage: ChatStreamSession['assistantMessage']): Promise<HydratedSnapshotApplicationResult> => {
    const result = await inputArguments.ownerDispatch.applySnapshot(session.conversationId, session.requestId, assistantMessage, false);
    if (result !== null) {
        return result;
    }
    applyAssistantMessageSnapshot(session, assistantMessage);
    return 'active';
};

const applyInactiveFollowerSnapshot = async (inputArguments: ActiveStatusInactiveTransitionArguments, session: ChatStreamSession, assistantMessage: ChatStreamSession['assistantMessage']): Promise<HydratedSnapshotApplicationResult> => {
    const result = await inputArguments.followerSessions.applyFollowerSnapshot(session.conversationId, session.requestId, assistantMessage, false);
    if (result !== null) {
        return result;
    }
    applyAssistantMessageSnapshot(session, assistantMessage);
    return 'active';
};

const terminalizeInactiveFollower = async (inputArguments: ActiveStatusInactiveTransitionArguments, conversationId: string, expectedRequestId: string): Promise<InactiveTerminalizationResult> => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return 'not-terminalized';
    }
    const session = inputArguments.sessions.get(normalizedConversationId);
    if (!session || session.transportMode !== 'follower' || session.requestId !== expectedRequestId) {
        return 'not-terminalized';
    }
    if (inputArguments.requestDispositions.shouldIgnorePassiveStreamEvent(session.conversationId, session.requestId)) {
        deactivateFollowerSession(inputArguments, normalizedConversationId, session);
        return 'suppressed';
    }
    const assistantMessage = await waitForInactiveTerminalSnapshot(
        inputArguments,
        {
            conversationId: session.conversationId,
            assistantTimestamp: session.assistantTimestamp,
            assistantTurnTimestamp: session.assistantTurnTimestamp,
            modelVariantIndex: session.modelVariantIndex
        },
        session.assistantMessage,
        false
    );
    if (!inputArguments.isCurrent()) {
        return 'not-terminalized';
    }
    const currentSession = inputArguments.sessions.get(normalizedConversationId);
    if (currentSession !== session || !currentSession.active || currentSession.transportMode !== 'follower' || currentSession.requestId !== expectedRequestId) {
        return 'not-terminalized';
    }
    if (assistantMessage === null) {
        return finalizeInactiveFollowerSession(inputArguments, session);
    }
    if ((await applyInactiveFollowerSnapshot(inputArguments, session, assistantMessage)) === 'terminal') {
        return 'hydrated-terminal';
    }
    return finalizeInactiveFollowerSession(inputArguments, session);
};

const finalizeInactiveOwnerSession = async (inputArguments: ActiveStatusInactiveTransitionArguments, status: InactiveTerminalStreamIdentity & { requestId: string }, session: ChatStreamSession, initialMessage: ChatStreamSession['assistantMessage']): Promise<InactiveTerminalizationResult> => {
    const assistantMessage = await waitForInactiveTerminalSnapshot(inputArguments, status, initialMessage, false);
    if (!inputArguments.isCurrent()) {
        return 'not-terminalized';
    }
    const currentSession = inputArguments.sessions.get(status.conversationId);
    if (currentSession !== session || !currentSession.active || currentSession.transportMode !== 'owner' || !sessionMatchesActiveStatus(currentSession, status)) {
        return 'not-terminalized';
    }
    if (assistantMessage === null) {
        finalizeChatStreamProtocolFailure({
            session,
            runtime: inputArguments.runtime,
            message: INACTIVE_TERMINAL_STATE_MISSING_MESSAGE,
            errorCode: 'protocol_error'
        });
        discardOwnerSession(inputArguments, status.conversationId, session);
        return 'missing-terminal-snapshot';
    }
    if ((await applyInactiveOwnerSnapshot(inputArguments, session, assistantMessage)) === 'terminal') {
        return 'hydrated-terminal';
    }
    const terminalStatus = resolveHydratedTerminalStatus(session);
    if (terminalStatus === null) {
        finalizeChatStreamProtocolFailure({
            session,
            runtime: inputArguments.runtime,
            message: INACTIVE_TERMINAL_STATE_MISSING_MESSAGE,
            errorCode: 'protocol_error'
        });
        discardOwnerSession(inputArguments, status.conversationId, session);
        return 'missing-terminal-snapshot';
    }
    finalizeChatStreamHydratedTerminal({
        session,
        runtime: inputArguments.runtime,
        status: terminalStatus,
        finishReason: terminalStatus === 'complete' ? (session.assistantMessage.finishReason ?? null) : terminalStatus,
        notifyUser: false
    });
    discardOwnerSession(inputArguments, status.conversationId, session);
    return 'hydrated-terminal';
};

const finalizeInactiveFollowerFromHydratedMessage = async (inputArguments: ActiveStatusInactiveTransitionArguments, session: ChatStreamSession, assistantMessage: ChatStreamSession['assistantMessage']): Promise<InactiveTerminalizationResult> => {
    if ((await applyInactiveFollowerSnapshot(inputArguments, session, assistantMessage)) === 'terminal') {
        return 'hydrated-terminal';
    }
    return finalizeInactiveFollowerSession(inputArguments, session);
};

export { finalizeInactiveFollowerFromHydratedMessage, finalizeInactiveOwnerSession, terminalizeInactiveFollower, waitForInactiveTerminalSnapshot };
export type { ActiveStatusInactiveTransitionArguments, InactiveTerminalizationResult };
