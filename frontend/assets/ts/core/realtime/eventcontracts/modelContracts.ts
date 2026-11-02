/* SoAI - Frontend model WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/modelContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { readRequiredTrimmedStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { readWebSocketBroadcastEnvelope } from '@core/realtime/eventcontracts/broadcastEnvelope.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

interface ModelDatabaseChangeEvent {
    eventId: string;
    timestamp: number;
    addedUniversalIds: string[];
    removedUniversalIds: string[];
}

interface ModelParametersChangedEvent {
    eventId: string;
    timestamp: number;
    universalId: string;
}

const decodeModelDatabaseChange = (payload: JsonValue): ModelDatabaseChangeEvent => {
    const { record, timestamp, eventId } = readWebSocketBroadcastEnvelope(payload, WEBSOCKET_EVENT_TYPES.MODEL_DATABASE_CHANGE, 'Model event');
    return {
        eventId,
        timestamp,
        addedUniversalIds: readRequiredTrimmedStringArrayValue(record['added_uids'], 'Model database change event.added_uids'),
        removedUniversalIds: readRequiredTrimmedStringArrayValue(record['removed_uids'], 'Model database change event.removed_uids')
    };
};

const decodeModelParametersChanged = (payload: JsonValue): ModelParametersChangedEvent => {
    const { record, timestamp, eventId } = readWebSocketBroadcastEnvelope(payload, WEBSOCKET_EVENT_TYPES.MODEL_PARAMETERS_CHANGED, 'Model event');
    return { timestamp, eventId, universalId: readRequiredTrimmedStringValue(record['universal_id'], 'Model parameters changed event.universal_id') };
};

const MODEL_EVENT_CONTRACTS = Object.freeze({
    databaseChanged: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.MODEL_DATABASE_CHANGE, decodeModelDatabaseChange),
    parametersChanged: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.MODEL_PARAMETERS_CHANGED, decodeModelParametersChanged)
});

export { MODEL_EVENT_CONTRACTS };
export type { ModelDatabaseChangeEvent, ModelParametersChangedEvent };
