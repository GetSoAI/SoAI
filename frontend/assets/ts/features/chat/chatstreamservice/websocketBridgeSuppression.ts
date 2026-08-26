/* SoAI - Chat stream WebSocket bridge suppression checks [frontend/assets/ts/features/chat/chatstreamservice/websocketBridgeSuppression.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatStreamEventEnvelope } from '@core/realtime/eventcontracts/chatStreamEnvelope.ts';
import type { StreamRequestDispositionRegistry } from '@features/chat/chatstreamservice/streamRequestDispositionRegistry.ts';
import type { ChatStreamCommandErrorEnvelope } from '@core/realtime/eventcontracts/chatStreamCommandError.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type StreamSuppressionScope = 'owner' | 'passive';

const isChatStreamRequestSuppressed = (requestDispositions: StreamRequestDispositionRegistry, conversationIdValue: string, requestIdValue: string, scope: StreamSuppressionScope): boolean => {
    const conversationId = normalizeConversationId(conversationIdValue);
    if (!conversationId) {
        return false;
    }
    const requestId = requestIdValue.trim();
    if (scope === 'passive') {
        return requestDispositions.shouldIgnorePassiveStreamEvent(conversationId, requestId);
    }
    return requestDispositions.isRequestSuppressed(conversationId, requestId);
};

const isSuppressedStreamEvent = (requestDispositions: StreamRequestDispositionRegistry, envelope: ChatStreamEventEnvelope, scope: StreamSuppressionScope): boolean => {
    return isChatStreamRequestSuppressed(requestDispositions, envelope.convId, envelope.requestId, scope);
};

const isSuppressedCommandErrorEvent = (requestDispositions: StreamRequestDispositionRegistry, envelope: ChatStreamCommandErrorEnvelope, scope: StreamSuppressionScope): boolean => {
    return isChatStreamRequestSuppressed(requestDispositions, envelope.convId, envelope.requestId, scope);
};

export { isSuppressedCommandErrorEvent, isSuppressedStreamEvent };
