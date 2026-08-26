/* SoAI - Frontend licensing WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/licensingContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { assertExactRecordKeys, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_PROTOCOL_VERSION } from '@core/websocketclient/constants.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

interface LicensingStatusChangedEvent {
    eventId: string;
    timestamp: number;
}

const decodeLicensingStatusChanged = (payload: JsonValue): LicensingStatusChangedEvent => {
    const record = requireRecord(payload, 'Licensing status changed event');
    assertExactRecordKeys(record, ['type', 'protocol_version', 'event_id', 'timestamp'], 'Licensing status changed event');
    const eventType = readRequiredTrimmedStringValue(record['type'], 'Licensing status changed event.type');
    if (eventType !== WEBSOCKET_EVENT_TYPES.LICENSING_STATUS_CHANGED) throw new TypeError('Licensing status changed event.type is invalid');
    const protocolVersion = readRequiredFiniteNumberValue(record['protocol_version'], 'Licensing status changed event.protocol_version');
    if (protocolVersion !== WEBSOCKET_PROTOCOL_VERSION) throw new TypeError('Licensing status changed event.protocol_version is unsupported');
    const timestamp = readRequiredFiniteNumberValue(record['timestamp'], 'Licensing status changed event.timestamp');
    if (timestamp <= 0) throw new TypeError('Licensing status changed event.timestamp must be positive');
    return {
        eventId: readRequiredTrimmedStringValue(record['event_id'], 'Licensing status changed event.event_id'),
        timestamp
    };
};

const LICENSING_EVENT_CONTRACTS = Object.freeze({
    statusChanged: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.LICENSING_STATUS_CHANGED, decodeLicensingStatusChanged)
});

export { LICENSING_EVENT_CONTRACTS };
export type { LicensingStatusChangedEvent };
