/* SoAI - Shared frontend WebSocket client snapshot payload [frontend/assets/ts/core/websocketclient/snapshotPayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonArray, isJsonObject, type JsonArray, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { requestWebSocketSnapshot } from '@core/websocketclient/service.ts';
import type { SnapshotRequestOptions } from '@core/websocketclient/types.ts';

const requestWebSocketSnapshotPayload = async (resourceName: string, parameters: JsonObject | null = null, options: SnapshotRequestOptions = {}): Promise<JsonValue> => {
    const snapshot = await requestWebSocketSnapshot(resourceName, parameters, options);
    if (snapshot.resource !== resourceName) {
        throw new Error(`WebSocket snapshot envelope is invalid for ${resourceName}`);
    }
    return snapshot.data ?? null;
};

const requestWebSocketSnapshotRecord = async (resourceName: string, parameters: JsonObject | null = null, options: SnapshotRequestOptions = {}): Promise<JsonObject> => {
    const payload = await requestWebSocketSnapshotPayload(resourceName, parameters, options);
    if (!isJsonObject(payload)) {
        throw new Error(`${resourceName} snapshot returned invalid payload`);
    }
    return payload;
};

const requestWebSocketSnapshotArray = async (resourceName: string, parameters: JsonObject | null = null, options: SnapshotRequestOptions = {}): Promise<JsonArray> => {
    const payload = await requestWebSocketSnapshotPayload(resourceName, parameters, options);
    if (!isJsonArray(payload)) {
        throw new Error(`${resourceName} snapshot returned invalid payload`);
    }
    return payload;
};

export { requestWebSocketSnapshotArray, requestWebSocketSnapshotPayload, requestWebSocketSnapshotRecord };
