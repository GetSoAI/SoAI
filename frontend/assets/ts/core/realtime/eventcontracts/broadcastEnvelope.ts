/* SoAI - Shared typed broadcast identity and protocol validation [frontend/assets/ts/core/realtime/eventcontracts/broadcastEnvelope.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_PROTOCOL_VERSION } from '@core/websocketclient/constants.ts';

const readWebSocketBroadcastEnvelope = (payload: JsonValue, expectedType: string, label: string) => {
    const record = requireRecord(payload, label);
    const eventType = readRequiredTrimmedStringValue(record['type'], `${label}.type`);
    if (eventType !== expectedType) throw new TypeError(`${label}.type is invalid`);
    const protocolVersion = readRequiredFiniteNumberValue(record['protocol_version'], `${label}.protocol_version`);
    if (protocolVersion !== WEBSOCKET_PROTOCOL_VERSION) throw new TypeError(`${label}.protocol_version is unsupported`);
    const timestamp = readRequiredFiniteNumberValue(record['timestamp'], `${label}.timestamp`);
    if (timestamp <= 0) throw new TypeError(`${label}.timestamp must be positive`);
    return { record, timestamp, eventId: readRequiredTrimmedStringValue(record['event_id'], `${label}.event_id`) };
};

export { readWebSocketBroadcastEnvelope };
