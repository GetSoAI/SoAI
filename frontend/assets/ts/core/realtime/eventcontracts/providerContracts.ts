/* SoAI - Frontend provider WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/providerContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

interface ProviderStatusUpdatedEvent {
    eventId: string;
    timestamp: number;
    pluginName: string;
    providerId: string;
    newStatus: string;
    error: string | null;
}

const decodeProviderStatusUpdated = (payload: JsonValue): ProviderStatusUpdatedEvent => {
    const record = requireRecord(payload, 'Provider status updated event');
    const timestamp = readRequiredFiniteNumberValue(record['timestamp'], 'Provider status updated event.timestamp');
    if (timestamp <= 0) throw new TypeError('Provider status updated event.timestamp must be positive');
    return {
        eventId: readRequiredTrimmedStringValue(record['event_id'], 'Provider status updated event.event_id'),
        timestamp,
        pluginName: readRequiredTrimmedStringValue(record['plugin_name'], 'Provider status updated event.plugin_name'),
        providerId: readRequiredTrimmedStringValue(record['provider_id'], 'Provider status updated event.provider_id'),
        newStatus: readRequiredTrimmedStringValue(record['new_status'], 'Provider status updated event.new_status'),
        error: readNullableTrimmedStringValue(record['error'], 'Provider status updated event.error')
    };
};

const PROVIDER_EVENT_CONTRACTS = Object.freeze({ statusUpdated: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.PROVIDER_STATUS_UPDATED, decodeProviderStatusUpdated) });

export { PROVIDER_EVENT_CONTRACTS };
export type { ProviderStatusUpdatedEvent };
