/* SoAI - Shared frontend WebSocket client events [frontend/assets/ts/core/websocketclient/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';
import { WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';
import { WEBSOCKET_PROTOCOL_VERSION } from '@core/websocketclient/constants.ts';
import { type WebSocketMessageData } from '@core/websocketclient/types.ts';

const resolveSnapshotId = (data: WebSocketMessageData): string | null => {
    const snapshotId = data.snapshotId;
    if (isString(snapshotId) && snapshotId.trim()) return snapshotId.trim();
    return null;
};

const resolveSnapshotErrorMessage = (data: WebSocketMessageData): string => {
    const errorField = data.error;
    if (isString(errorField) && errorField.trim()) return errorField.trim();
    const message = data.message;
    if (isString(message) && message.trim()) return message.trim();
    if (isJsonObject(errorField)) {
        const errorObject = errorField;
        const errorMessage = errorObject['message'];
        if (isString(errorMessage) && errorMessage.trim()) return errorMessage.trim();
        const nested = errorObject['error'];
        if (isJsonObject(nested)) {
            const nestedObject = nested;
            const nestedMessage = nestedObject['message'];
            if (isString(nestedMessage) && nestedMessage.trim()) return nestedMessage.trim();
        }
    }
    return 'Snapshot request failed';
};

const resolveSnapshotTraceId = (data: WebSocketMessageData): string | undefined => {
    const topLevel = data.raw['trace_id'];
    if (isString(topLevel) && topLevel.trim()) return topLevel.trim();
    const errorField = data.error;
    if (!isJsonObject(errorField)) return undefined;
    const nested = errorField['trace_id'];
    if (isString(nested) && nested.trim()) return nested.trim();
    const errorNested = errorField['error'];
    if (!isJsonObject(errorNested)) return undefined;
    const deep = errorNested['trace_id'];
    if (isString(deep) && deep.trim()) return deep.trim();
    return undefined;
};

const serializeSnapshotRequest = (payload: JsonObject | null, resourceName: string, tabId: string, snapshotId: string): JsonObject => {
    const baseParameters = payload && isJsonObject(payload) ? { ...payload } : {};
    return {
        type: WEBSOCKET_MESSAGE_TYPES.REQUEST_SNAPSHOT,
        resource: resourceName,
        'snapshot_id': snapshotId,
        'tab_id': tabId,
        'protocol_version': WEBSOCKET_PROTOCOL_VERSION,
        payload: baseParameters
    };
};

export { resolveSnapshotErrorMessage, resolveSnapshotId, resolveSnapshotTraceId, serializeSnapshotRequest };
