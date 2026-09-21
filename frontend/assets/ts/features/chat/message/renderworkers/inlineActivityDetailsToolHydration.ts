/* SoAI - Expanded inline tool activity detail hydration [frontend/assets/ts/features/chat/message/renderworkers/inlineActivityDetailsToolHydration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNonNegativeInteger } from '@core/typeGuards.ts';
import { requestWebSocketSnapshotPayload } from '@core/websocketclient/snapshotPayload.ts';
import { serializeToolCallSnapshotRequest } from '@core/api/contracts/chatRealtimeSnapshotContracts.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { mapAssistantTimelineToolPayload } from '@features/chat/assistanteventtimeline/toolPayloadMapper.ts';
import type { InlineActivityLookupType } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { canRequestPersistedToolCallSnapshot } from '@features/chat/toolactivity/toolCallSnapshotEligibility.ts';
import { upsertToolCallProjection } from '@features/chat/toolactivity/toolProjectionMutation.ts';
import { messageContainsToolDetailHydrationCandidate, toolProjectionProvidesHydratedDetails } from '@features/chat/toolactivity/toolDetailsHydrationPolicy.ts';

interface InlineActivityDetailsHydrationRequest {
    conversationId: string;
    message: ChatMessage;
    expectedType: InlineActivityLookupType;
    callId: string;
    signal: AbortSignal;
}

const resolveAssistantTurnTimestamp = (message: ChatMessage): number | null => {
    const assistantTurnAtMs = message.assistantTurnAtMs;
    if (isNonNegativeInteger(assistantTurnAtMs) && assistantTurnAtMs > 0) {
        return assistantTurnAtMs;
    }
    const timestamp = message.timestamp;
    return isNonNegativeInteger(timestamp) && timestamp > 0 ? timestamp : null;
};

const resolveModelVariantIndex = (message: ChatMessage): number | null => {
    const modelVariantIndex = message.modelVariantIndex;
    return isNonNegativeInteger(modelVariantIndex) ? modelVariantIndex : null;
};

const hydrateInlineToolDetailsMessage = async (request: InlineActivityDetailsHydrationRequest): Promise<ChatMessage> => {
    if (request.expectedType !== 'inline_tool_activity') {
        return request.message;
    }
    const normalizedCallId = request.callId.trim();
    if (!normalizedCallId) {
        return request.message;
    }
    if (!canRequestPersistedToolCallSnapshot(normalizedCallId)) {
        return request.message;
    }
    if (!messageContainsToolDetailHydrationCandidate(request.message, normalizedCallId)) {
        return request.message;
    }
    const assistantTurnAtMs = resolveAssistantTurnTimestamp(request.message);
    const modelVariantIndex = resolveModelVariantIndex(request.message);
    if (assistantTurnAtMs === null || modelVariantIndex === null) {
        return request.message;
    }
    const snapshot = await requestWebSocketSnapshotPayload(
        'webui.chat.tool_calls.by_call_id',
        serializeToolCallSnapshotRequest({
            conversationId: request.conversationId,
            callId: normalizedCallId,
            assistantTurnAtMs: assistantTurnAtMs,
            modelVariantIndex: modelVariantIndex
        }),
        { signal: request.signal }
    );
    const projection = mapAssistantTimelineToolPayload(snapshot);
    if (projection === null || projection.callId !== normalizedCallId || !toolProjectionProvidesHydratedDetails(projection)) {
        return request.message;
    }
    const hydratedMessage: ChatMessage = {
        ...request.message,
        toolCallProjections: Array.isArray(request.message.toolCallProjections) ? [...request.message.toolCallProjections] : []
    };
    upsertToolCallProjection(hydratedMessage, projection);
    return hydratedMessage;
};

export { hydrateInlineToolDetailsMessage };
