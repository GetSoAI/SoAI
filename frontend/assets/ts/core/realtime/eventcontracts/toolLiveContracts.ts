/* SoAI - Frontend live tool WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/toolLiveContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { readRequiredFiniteNumberValue, readRequiredNonNegativeIntegerValue, readRequiredPositiveIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';
import { requireAssistantTimelineTool } from '@core/realtime/eventcontracts/assistantToolContracts.ts';
import type { AssistantTimelineTool } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';

interface ToolCallLiveUpdatedEvent {
    eventId: string;
    timestamp: number;
    userId: number;
    convId: string;
    requestId: string | null;
    assistantAtMs: number;
    assistantTurnAtMs: number;
    modelVariantIndex: number;
    callId: string;
    liveSequence: number;
    liveRevision: number;
    lastLiveEventAtMs: number;
    eventType: string;
    tool: AssistantTimelineTool;
}

const decodeToolCallLiveUpdated = (payload: JsonValue): ToolCallLiveUpdatedEvent => {
    const record = requireRecord(payload, 'Tool call live updated event');
    const timestamp = readRequiredFiniteNumberValue(record['timestamp'], 'Tool call live updated event.timestamp');
    if (timestamp <= 0) throw new TypeError('Tool call live updated event.timestamp must be positive');
    return {
        eventId: readRequiredTrimmedStringValue(record['event_id'], 'Tool call live updated event.event_id'),
        timestamp,
        userId: readRequiredPositiveIntegerValue(record['user_id'], 'Tool call live updated event.user_id'),
        convId: readRequiredTrimmedStringValue(record['conv_id'], 'Tool call live updated event.conv_id'),
        requestId: readNullableTrimmedStringValue(record['request_id'], 'Tool call live updated event.request_id'),
        assistantAtMs: readRequiredNonNegativeIntegerValue(record['assistant_at_ms'], 'Tool call live updated event.assistant_at_ms'),
        assistantTurnAtMs: readRequiredNonNegativeIntegerValue(record['assistant_turn_at_ms'], 'Tool call live updated event.assistant_turn_at_ms'),
        modelVariantIndex: readRequiredNonNegativeIntegerValue(record['model_variant_index'], 'Tool call live updated event.model_variant_index'),
        callId: readRequiredTrimmedStringValue(record['call_id'], 'Tool call live updated event.call_id'),
        liveSequence: readRequiredNonNegativeIntegerValue(record['live_sequence'], 'Tool call live updated event.live_sequence'),
        liveRevision: readRequiredPositiveIntegerValue(record['live_revision'], 'Tool call live updated event.live_revision'),
        lastLiveEventAtMs: readRequiredPositiveIntegerValue(record['last_live_event_at_ms'], 'Tool call live updated event.last_live_event_at_ms'),
        eventType: readRequiredTrimmedStringValue(record['event_type'], 'Tool call live updated event.event_type'),
        tool: requireAssistantTimelineTool(record['tool'], 'Tool call live updated event.tool')
    };
};

const TOOL_LIVE_EVENT_CONTRACTS = Object.freeze({ updated: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.TOOL_CALL_LIVE_UPDATED, decodeToolCallLiveUpdated) });

export { TOOL_LIVE_EVENT_CONTRACTS };
export type { ToolCallLiveUpdatedEvent };
