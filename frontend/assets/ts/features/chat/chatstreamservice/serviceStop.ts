/* SoAI - Chat stream service stop coordination [frontend/assets/ts/features/chat/chatstreamservice/serviceStop.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { getWebUiUserCancellationReason } from '@core/tasks/cancellationReasons.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { isString } from '@core/typeGuards.ts';
import { resolvePendingStop, storePendingStop, type PendingStopRequest } from '@features/chat/chatstreamservice/pendingStopRequests.ts';
import type { ChatStopOutcome, ChatStreamStopOperationOwner } from '@features/chat/chatstreamservice/stopOperationOwner.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const resolveStopReason = (reason: string | undefined): string => (isString(reason) && reason.trim() ? reason.trim() : getWebUiUserCancellationReason());

type StopChatStreamSessionArguments = {
    sessions: Map<string, ChatStreamSession>;
    pendingStopRequests: Map<string, PendingStopRequest>;
    stopOperations: ChatStreamStopOperationOwner;
    conversationId: string;
    reason?: string;
    requestId?: string;
    force?: boolean;
    forcePendingSteers?: boolean;
    onTerminalEvidence?: () => void;
};

const resolveStopRequest = (pendingStopRequests: Map<string, PendingStopRequest>, conversationId: string, requestId: string, nowMs: number): { reason: string; forcePendingSteers: boolean } | null => resolvePendingStop(pendingStopRequests, conversationId, requestId, nowMs);

const stopChatStreamSession = (inputArguments: StopChatStreamSessionArguments): Promise<ChatStopOutcome> | null => {
    const conversationId = normalizeConversationId(inputArguments.conversationId);
    const requestedId = toTrimmedString(inputArguments.requestId);
    if (!conversationId) return null;
    const session = inputArguments.sessions.get(conversationId);
    const requestId = requestedId || (session?.active === true ? session.requestId : null);
    if (!requestId) return null;
    if (session?.active === true && session.requestId !== requestId && inputArguments.force !== true) return null;
    const reason = resolveStopReason(inputArguments.reason);
    const forcePendingSteers = inputArguments.forcePendingSteers === true;
    if (session?.active === true && session.requestId === requestId && session.status === 'streaming') {
        session.stopOperationPending = true;
    } else {
        storePendingStop(inputArguments.pendingStopRequests, conversationId, requestId, reason, forcePendingSteers, monotonicMs());
    }
    return inputArguments.stopOperations.request({
        conversationId,
        requestId,
        forcePendingSteers,
        ...(inputArguments.onTerminalEvidence === undefined ? {} : { onTerminalEvidence: inputArguments.onTerminalEvidence })
    });
};

export { resolveStopRequest, stopChatStreamSession };
