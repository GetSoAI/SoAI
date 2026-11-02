/* SoAI - Serialized filesystem invalidation broadcast contract [frontend/assets/ts/core/realtime/eventcontracts/fileSystemContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { readWebSocketBroadcastEnvelope } from '@core/realtime/eventcontracts/broadcastEnvelope.ts';
import { readRequiredBooleanValue, readRequiredEnumValue, readRequiredNonEmptyStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

interface FileSystemChangedEvent {
    readonly eventId: string;
    readonly timestamp: number;
    readonly operation: 'create' | 'update' | 'delete' | 'move' | 'copy' | 'mkdir';
    readonly virtualPath: string;
    readonly isDirectory: boolean;
    readonly destinationVirtualPath: string | null;
}

const decodeFileSystemChanged = (payload: JsonValue): FileSystemChangedEvent => {
    const { record, timestamp, eventId } = readWebSocketBroadcastEnvelope(payload, WEBSOCKET_EVENT_TYPES.FILE_SYSTEM_CHANGED, 'File system event');
    return {
        eventId,
        timestamp,
        operation: readRequiredEnumValue(record['operation'], 'File system event.operation', ['create', 'update', 'delete', 'move', 'copy', 'mkdir']),
        virtualPath: readRequiredNonEmptyStringValue(record['virtual_path'], 'File system event.virtual_path'),
        isDirectory: readRequiredBooleanValue(record['is_directory'], 'File system event.is_directory'),
        destinationVirtualPath: record['destination_virtual_path'] === null ? null : readRequiredNonEmptyStringValue(record['destination_virtual_path'], 'File system event.destination_virtual_path')
    };
};

const FILE_SYSTEM_EVENT_CONTRACTS = Object.freeze({ changed: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.FILE_SYSTEM_CHANGED, decodeFileSystemChanged) });

export { FILE_SYSTEM_EVENT_CONTRACTS };
export type { FileSystemChangedEvent };
