/* SoAI - Chat stream service stop coordination [frontend/assets/ts/features/chat/chatstreamservice/serviceStop.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { getWebUiUserCancellationReason } from '@core/tasks/cancellationReasons.ts';
import { isString } from '@core/typeGuards.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { resolvePendingStop, storePendingStop, type PendingStopRequest } from '@features/chat/chatstreamservice/pendingStopRequests.ts';
import { requestChatStreamCancel, requestChatStreamCancelByIdentity } from '@features/chat/chatstreamservice/streamCancel.ts';
import type { StreamRequestDispositionRegistry } from '@features/chat/chatstreamservice/streamRequestDispositionRegistry.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const resolveStopReason = (reason: string | undefined): string => {
    return isString(reason) && reason.trim() ? reason.trim() : getWebUiUserCancellationReason();
};

type StopChatStreamSessionArguments = {
    sessions: Map<string, ChatStreamSession>;
    pendingStopRequests: Map<string, PendingStopRequest>;
    requestDispositions: StreamRequestDispositionRegistry;
    conversationId: string;
    reason?: string;
    requestId?: string;
    force?: boolean;
    forcePendingSteers?: boolean;
};

const resolveStopRequest = (pendingStopRequests: Map<string, PendingStopRequest>, conversationId: string, requestId: string, nowMs: number): { reason: string; forcePendingSteers: boolean } | null => {
    return resolvePendingStop(pendingStopRequests, conversationId, requestId, nowMs);
};

const stopChatStreamSession = (inputArguments: StopChatStreamSessionArguments): void => {
    const normalizedConversationId = normalizeConversationId(inputArguments.conversationId);
    const normalizedRequestId = toTrimmedString(inputArguments.requestId);
    const forceStop = inputArguments.force === true;
    const forcePendingSteers = inputArguments.forcePendingSteers === true;
    if (!normalizedConversationId) {
        return;
    }
    const normalizedReason = resolveStopReason(inputArguments.reason);
    const session = inputArguments.sessions.get(normalizedConversationId);
    if (!session || !session.active) {
        requestChatStreamCancelByIdentity({
            conversationId: normalizedConversationId,
            requestId: normalizedRequestId ? normalizedRequestId : null,
            reason: normalizedReason,
            forcePendingSteers
        });
        if (normalizedRequestId) {
            const nowMs = monotonicMs();
            storePendingStop(inputArguments.pendingStopRequests, normalizedConversationId, normalizedRequestId, normalizedReason, forcePendingSteers, nowMs);
            inputArguments.requestDispositions.markFollowerQuarantine(normalizedConversationId, normalizedRequestId);
        }
        return;
    }

    if (normalizedRequestId && session.requestId !== normalizedRequestId) {
        if (forceStop) {
            requestChatStreamCancelByIdentity({
                conversationId: normalizedConversationId,
                requestId: normalizedRequestId,
                reason: normalizedReason,
                forcePendingSteers
            });
            inputArguments.requestDispositions.markFollowerQuarantine(normalizedConversationId, normalizedRequestId);
        }
        return;
    }

    if (session.status === 'streaming') {
        session.pendingCancellation = { reason: normalizedReason, forcePendingSteers };
        if (session.transportMode === 'owner') {
            inputArguments.requestDispositions.markFollowerQuarantine(normalizedConversationId, session.requestId);
        }
    }
    if (forceStop || session.status === 'streaming') {
        requestChatStreamCancel(session, normalizedReason, forcePendingSteers);
    }
    if (session.transportMode === 'follower' && session.status === 'streaming') {
        return;
    }
    session.abortController.abort();
};

export { resolveStopRequest, stopChatStreamSession };
