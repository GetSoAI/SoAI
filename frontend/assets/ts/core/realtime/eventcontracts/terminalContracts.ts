/* SoAI - Frontend terminal WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/terminalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import { readRequiredBooleanValue, readRequiredStringValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { readRequiredFiniteIntegerValue, readRequiredPositiveIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

interface PtyConnectedEvent {
    sessionId: string;
    shell: string;
    columns: number;
    rows: number;
    processId: number;
}

interface PtyOutputEvent {
    sessionId: string;
    data: string;
}

interface PtyExitedEvent {
    sessionId: string;
    exitCode: number;
}

interface PtyDisconnectedEvent {
    sessionId: string;
}

interface PtyBusyEvent {
    sessionId: string;
    busy: boolean;
}

interface PtyErrorEvent {
    code: string | number;
    message: string;
    traceId: string | null;
    details: OpaqueJsonObject | null;
}

const requireSessionId = (record: Record<string, JsonValue>, label: string): string => readRequiredTrimmedStringValue(record['session_id'], `${label}.session_id`);

const decodeConnected = (payload: JsonValue): PtyConnectedEvent => {
    const record = requireRecord(payload, 'PTY connected event');
    return {
        sessionId: requireSessionId(record, 'PTY connected event'),
        shell: readRequiredTrimmedStringValue(record['shell'], 'PTY connected event.shell'),
        columns: readRequiredPositiveIntegerValue(record['cols'], 'PTY connected event.cols'),
        rows: readRequiredPositiveIntegerValue(record['rows'], 'PTY connected event.rows'),
        processId: readRequiredPositiveIntegerValue(record['pid'], 'PTY connected event.pid')
    };
};

const decodeOutput = (payload: JsonValue): PtyOutputEvent => {
    const record = requireRecord(payload, 'PTY output event');
    return { sessionId: requireSessionId(record, 'PTY output event'), data: readRequiredStringValue(record['data'], 'PTY output event.data') };
};

const decodeExited = (payload: JsonValue): PtyExitedEvent => {
    const record = requireRecord(payload, 'PTY exited event');
    return { sessionId: requireSessionId(record, 'PTY exited event'), exitCode: readRequiredFiniteIntegerValue(record['exit_code'], 'PTY exited event.exit_code') };
};

const decodeDisconnected = (payload: JsonValue): PtyDisconnectedEvent => {
    const record = requireRecord(payload, 'PTY disconnected event');
    return { sessionId: requireSessionId(record, 'PTY disconnected event') };
};

const decodeBusy = (payload: JsonValue): PtyBusyEvent => {
    const record = requireRecord(payload, 'PTY busy event');
    return { sessionId: requireSessionId(record, 'PTY busy event'), busy: readRequiredBooleanValue(record['busy'], 'PTY busy event.busy') };
};

const decodeError = (payload: JsonValue): PtyErrorEvent => {
    const record = requireRecord(payload, 'PTY error event');
    const error = requireRecord(record['error'], 'PTY error event.error');
    const codeValue = error['code'];
    if ((typeof codeValue !== 'string' || !codeValue.trim()) && (typeof codeValue !== 'number' || !Number.isFinite(codeValue))) throw new TypeError('PTY error event.error.code must be a string or finite number');
    const traceIdValue = error['trace_id'];
    const traceId = traceIdValue === null || traceIdValue === undefined ? null : readRequiredTrimmedStringValue(traceIdValue, 'PTY error event.trace_id');
    const detailsValue = error['details'];
    const details = detailsValue === null || detailsValue === undefined ? null : requireRecord(detailsValue, 'PTY error event.error.details');
    return { code: codeValue, message: readRequiredStringValue(record['message'], 'PTY error event.message'), traceId, details };
};

const TERMINAL_EVENT_CONTRACTS = Object.freeze({
    connected: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.PTY_CONNECTED, decodeConnected),
    output: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.PTY_OUTPUT, decodeOutput),
    exited: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.PTY_EXITED, decodeExited),
    disconnected: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.PTY_DISCONNECTED, decodeDisconnected),
    error: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.PTY_ERROR, decodeError),
    busy: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.PTY_BUSY, decodeBusy)
});

export { TERMINAL_EVENT_CONTRACTS };
export type { PtyBusyEvent, PtyConnectedEvent, PtyDisconnectedEvent, PtyErrorEvent, PtyExitedEvent, PtyOutputEvent };
