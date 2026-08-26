/* SoAI - Frontend lifecycle WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/lifecycleContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { readOptionalFiniteNumberValue, readOptionalStringValue, readRequiredEnumValue, readRequiredStringValue } from '@core/types/payloadValueReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_LIFECYCLE_EVENT_TYPES } from '@core/websocketEvents.ts';

interface WebSocketConnectedEvent {
    url: string;
}

interface WebSocketDisconnectedEvent {
    code?: number;
    reason: string;
    sessionClosure: 'invalidate' | 'none' | 'rotate';
}

const decodeConnectedEvent = (payload: JsonValue): WebSocketConnectedEvent => {
    const record = requireRecord(payload, 'WebSocket connected event');
    return { url: readRequiredStringValue(record['url'], 'WebSocket connected event.url') };
};

const decodeDisconnectedEvent = (payload: JsonValue): WebSocketDisconnectedEvent => {
    const record = requireRecord(payload, 'WebSocket disconnected event');
    const code = readOptionalFiniteNumberValue(record['code'], 'WebSocket disconnected event.code');
    const reason = readOptionalStringValue(record['reason'], 'WebSocket disconnected event.reason') ?? '';
    const sessionClosure = readRequiredEnumValue(record['session_closure'], 'WebSocket disconnected event.session_closure', ['invalidate', 'none', 'rotate']);
    return { ...(code === undefined ? {} : { code }), reason, sessionClosure };
};

const LIFECYCLE_EVENT_CONTRACTS = Object.freeze({
    connected: defineWebSocketEventContract(WEBSOCKET_LIFECYCLE_EVENT_TYPES.CONNECTED, decodeConnectedEvent),
    disconnected: defineWebSocketEventContract(WEBSOCKET_LIFECYCLE_EVENT_TYPES.DISCONNECTED, decodeDisconnectedEvent)
});

export { LIFECYCLE_EVENT_CONTRACTS };
export type { WebSocketConnectedEvent, WebSocketDisconnectedEvent };
