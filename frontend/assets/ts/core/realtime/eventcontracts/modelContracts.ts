/* SoAI - Frontend model WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/modelContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { readRequiredTrimmedStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_PROTOCOL_VERSION } from '@core/websocketclient/constants.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

interface ModelDatabaseChangeEvent {
    eventId: string;
    timestamp: number;
    addedUniversalIds: string[];
    removedUniversalIds: string[];
}

const decodeModelDatabaseChange = (payload: JsonValue): ModelDatabaseChangeEvent => {
    const record = requireRecord(payload, 'Model database change event');
    const eventType = readRequiredTrimmedStringValue(record['type'], 'Model database change event.type');
    if (eventType !== WEBSOCKET_EVENT_TYPES.MODEL_DATABASE_CHANGE) throw new TypeError('Model database change event.type is invalid');
    const protocolVersion = readRequiredFiniteNumberValue(record['protocol_version'], 'Model database change event.protocol_version');
    if (protocolVersion !== WEBSOCKET_PROTOCOL_VERSION) throw new TypeError('Model database change event.protocol_version is unsupported');
    const timestamp = readRequiredFiniteNumberValue(record['timestamp'], 'Model database change event.timestamp');
    if (timestamp <= 0) throw new TypeError('Model database change event.timestamp must be positive');
    return {
        eventId: readRequiredTrimmedStringValue(record['event_id'], 'Model database change event.event_id'),
        timestamp,
        addedUniversalIds: readRequiredTrimmedStringArrayValue(record['added_uids'], 'Model database change event.added_uids'),
        removedUniversalIds: readRequiredTrimmedStringArrayValue(record['removed_uids'], 'Model database change event.removed_uids')
    };
};

const MODEL_EVENT_CONTRACTS = Object.freeze({ databaseChanged: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.MODEL_DATABASE_CHANGE, decodeModelDatabaseChange) });

export { MODEL_EVENT_CONTRACTS };
export type { ModelDatabaseChangeEvent };
