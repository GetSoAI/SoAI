/* SoAI - Frontend history reset WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/historyResetContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

interface HistoryResetEvent {
    clearedThroughMs: number;
}

const createHistoryResetDecoder =
    (label: string) =>
    (payload: JsonValue): HistoryResetEvent => {
        const record = requireRecord(payload, label);
        return { clearedThroughMs: readRequiredNonNegativeIntegerValue(record['cleared_through_ms'], `${label}.cleared_through_ms`) };
    };

const HISTORY_RESET_EVENT_CONTRACTS = Object.freeze({
    metrics: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.METRICS_HISTORY_RESET, createHistoryResetDecoder('Metrics history reset event')),
    hardware: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.HARDWARE_HISTORY_RESET, createHistoryResetDecoder('Hardware history reset event'))
});

export { HISTORY_RESET_EVENT_CONTRACTS };
export type { HistoryResetEvent };
