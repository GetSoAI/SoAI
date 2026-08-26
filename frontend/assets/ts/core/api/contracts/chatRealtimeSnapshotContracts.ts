/* SoAI - Frontend chat realtime snapshot request boundary contracts [frontend/assets/ts/core/api/contracts/chatRealtimeSnapshotContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { hasOwn, isNonNegativeInteger } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface ToolCallSnapshotRequest {
    conversationId: string;
    callId: string;
    assistantTurnAtMs: number;
    modelVariantIndex: number;
}

interface ToolCallLiveEventsPageRequest extends ToolCallSnapshotRequest {
    limit: number;
    beforeLiveSequence?: number | undefined;
}

interface ToolCallLiveEventsPage extends JsonObject {
    events: JsonValue[];
    nextBeforeLiveSequence: number | null;
}

const serializeConversationSnapshotRequest = (conversationId: string): JsonObject => ({ 'conv_id': conversationId });

const serializeToolCallSnapshotRequest = (request: ToolCallSnapshotRequest): JsonObject => ({
    'conv_id': request.conversationId,
    'call_id': request.callId,
    'assistant_turn_at_ms': request.assistantTurnAtMs,
    'model_variant_index': request.modelVariantIndex
});

const serializeToolCallLiveEventsPageRequest = (request: ToolCallLiveEventsPageRequest): JsonObject => {
    const serialized: JsonObject = {
        ...serializeToolCallSnapshotRequest(request),
        limit: request.limit
    };
    if (request.beforeLiveSequence !== undefined) serialized['before_live_sequence'] = request.beforeLiveSequence;
    return serialized;
};

const decodeToolCallLiveEventsPage = (value: JsonValue): ToolCallLiveEventsPage => {
    const record = requireRecord(value, 'Tool call live events page');
    if (hasOwn(record, 'nextBeforeLiveSequence')) throw new TypeError('Tool call live events page must use canonical V1 wire fields');
    if (!Array.isArray(record['events'])) throw new TypeError('Tool call live events page.events must be an array');
    const nextBeforeLiveSequence = record['next_before_live_sequence'];
    if (nextBeforeLiveSequence !== null && nextBeforeLiveSequence !== undefined && !isNonNegativeInteger(nextBeforeLiveSequence)) throw new TypeError('Tool call live events page.next_before_live_sequence must be a non-negative integer or null');
    return { events: record['events'], nextBeforeLiveSequence: nextBeforeLiveSequence ?? null };
};

export { decodeToolCallLiveEventsPage, serializeConversationSnapshotRequest, serializeToolCallLiveEventsPageRequest, serializeToolCallSnapshotRequest };
export type { ToolCallLiveEventsPage, ToolCallLiveEventsPageRequest, ToolCallSnapshotRequest };
