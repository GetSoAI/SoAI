/* SoAI - Owner-scoped chat library events [frontend/assets/ts/core/realtime/eventcontracts/chatLibraryContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredPositiveIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredNonEmptyStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

const decodeLibraryChange = (payload: JsonValue): { userId: number; eventId: string } => {
    const record = requireRecord(payload, 'Chat library event');
    return { userId: readRequiredPositiveIntegerValue(record['user_id'], 'Library owner'), eventId: readRequiredNonEmptyStringValue(record['event_id'], 'Library event identity') };
};

const CHAT_LIBRARY_EVENT_CONTRACTS = Object.freeze({
    memoryChanged: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.MEMORY_LIBRARY_CHANGED, decodeLibraryChange),
    presetsChanged: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.CHAT_PRESET_LIBRARY_CHANGED, decodeLibraryChange)
});

export { CHAT_LIBRARY_EVENT_CONTRACTS };
