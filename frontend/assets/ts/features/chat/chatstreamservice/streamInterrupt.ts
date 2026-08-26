/* SoAI - Chat stream interrupt coordination [frontend/assets/ts/features/chat/chatstreamservice/streamInterrupt.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getWebUiUserCancellationReason } from '@core/tasks/cancellationReasons.ts';
import { isString } from '@core/typeGuards.ts';
import type { ChatStreamOwnerDispatch } from '@features/chat/chatstreamservice/ownerDispatch.ts';
import type { RetainedToolTimelineCoordinator } from '@features/chat/chatstreamservice/retainedToolTimelineCoordinator.ts';
import { requestChatStreamCancelByIdentity } from '@features/chat/chatstreamservice/streamCancel.ts';
import type { ChatStreamNotificationRequestClearer } from '@features/chat/chatstreamservice/streamNotificationQueue.ts';
import type { StreamRequestDispositionRegistry } from '@features/chat/chatstreamservice/streamRequestDispositionRegistry.ts';
import { applyChatStreamTerminalState } from '@features/chat/chatstreamservice/streamTerminalState.ts';
import type { ChatStreamSession, InterruptedStreamSnapshot } from '@features/chat/chatstreamservice/types.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

interface StreamInterruptBridge {
    disposeFollowerRequest(conversationId: string, requestId: string): void;
    syncActiveStatusReconciliation(): void;
}

type InterruptChatStreamSessionArguments = {
    sessions: Map<string, ChatStreamSession>;
    requestDispositions: StreamRequestDispositionRegistry;
    notificationQueue: ChatStreamNotificationRequestClearer;
    runtime: StreamRuntime;
    ownerDispatch: ChatStreamOwnerDispatch;
    retainedToolTimeline: RetainedToolTimelineCoordinator;
    wsBridge: StreamInterruptBridge;
    conversationId: string;
    requestId?: string | null;
    reason?: string | null;
};

const normalizeInterruptReason = (reason: string | null | undefined): string => {
    if (isString(reason) && reason.trim()) {
        return reason.trim();
    }
    return getWebUiUserCancellationReason();
};

const buildInterruptedSnapshot = (session: ChatStreamSession): InterruptedStreamSnapshot => ({
    conversationId: session.conversationId,
    requestId: session.requestId,
    assistantMessage: session.assistantMessage,
    assistantTimestamp: session.assistantTimestamp,
    assistantTurnTimestamp: session.assistantTurnTimestamp,
    modelVariantIndex: session.modelVariantIndex
});

const interruptChatStreamSession = (inputArguments: InterruptChatStreamSessionArguments): InterruptedStreamSnapshot | null => {
    const conversationId = normalizeConversationId(inputArguments.conversationId);
    if (!conversationId) {
        return null;
    }
    const activeSession = inputArguments.sessions.get(conversationId) ?? null;
    const requestId = isString(inputArguments.requestId) && inputArguments.requestId.trim() ? inputArguments.requestId.trim() : (activeSession?.requestId ?? null);
    if (!requestId) {
        return null;
    }
    const reason = normalizeInterruptReason(inputArguments.reason);
    if (!activeSession || activeSession.requestId !== requestId) {
        inputArguments.requestDispositions.markInterrupt(conversationId, requestId);
        inputArguments.notificationQueue.clearRequest(conversationId, requestId);
        inputArguments.ownerDispatch.unregisterConversation(conversationId, requestId);
        inputArguments.retainedToolTimeline.clearRequest(conversationId, requestId);
        inputArguments.wsBridge.disposeFollowerRequest(conversationId, requestId);
        requestChatStreamCancelByIdentity({ conversationId, requestId, reason, forcePendingSteers: false });
        return null;
    }
    activeSession.pendingCancellation = { reason };
    applyChatStreamTerminalState({
        session: activeSession,
        status: 'cancelled',
        finishReason: 'cancelled',
        lastError: null,
        errorMessage: null,
        errorCode: null,
        referenceId: null
    });
    inputArguments.runtime.notify(activeSession, { type: 'terminal' });
    inputArguments.requestDispositions.markInterrupt(conversationId, requestId);
    inputArguments.ownerDispatch.unregisterConversation(conversationId, requestId);
    inputArguments.retainedToolTimeline.clearRequest(conversationId, requestId);
    inputArguments.wsBridge.disposeFollowerRequest(conversationId, requestId);
    activeSession.active = false;
    if (inputArguments.sessions.get(conversationId) === activeSession) {
        inputArguments.sessions.delete(conversationId);
    }
    inputArguments.wsBridge.syncActiveStatusReconciliation();
    activeSession.abortController.abort();
    requestChatStreamCancelByIdentity({ conversationId, requestId, reason, forcePendingSteers: false });
    return buildInterruptedSnapshot(activeSession);
};

export { interruptChatStreamSession };
export type { StreamInterruptBridge };
