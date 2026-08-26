/* SoAI - Chat feature pending stop requests [frontend/assets/ts/features/chat/chatstreamservice/pendingStopRequests.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const PENDING_STOP_REQUEST_TTL_MS = 4000;

interface PendingStopRequest {
    forcePendingSteers: boolean;
    reason: string;
    requestId: string;
    expiresAtMs: number;
}

const resolvePendingStop = (pendingStopRequests: Map<string, PendingStopRequest>, conversationId: string, requestId: string, nowMs: number): { reason: string; forcePendingSteers: boolean } | null => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return null;
    }
    const pendingStop = pendingStopRequests.get(normalizedConversationId);
    if (!pendingStop) {
        return null;
    }
    if (pendingStop.expiresAtMs <= nowMs) {
        pendingStopRequests.delete(normalizedConversationId);
        return null;
    }
    if (pendingStop.requestId !== requestId) {
        pendingStopRequests.delete(normalizedConversationId);
        return null;
    }
    pendingStopRequests.delete(normalizedConversationId);
    return { reason: pendingStop.reason, forcePendingSteers: pendingStop.forcePendingSteers };
};

const storePendingStop = (pendingStopRequests: Map<string, PendingStopRequest>, conversationId: string, requestId: string, reason: string, forcePendingSteers: boolean, nowMs: number): void => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return;
    }
    pendingStopRequests.set(normalizedConversationId, {
        reason,
        forcePendingSteers,
        requestId,
        expiresAtMs: nowMs + PENDING_STOP_REQUEST_TTL_MS
    });
};

export { resolvePendingStop, storePendingStop };
export type { PendingStopRequest };
