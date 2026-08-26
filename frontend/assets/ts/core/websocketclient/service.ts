/* SoAI - Shared frontend WebSocket client service [frontend/assets/ts/core/websocketclient/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CONNECTION_STATES } from '@core/websocketclient/constants.ts';
import { SnapshotError, SnapshotProtocolError } from '@core/websocketclient/snapshotManager.ts';
import { WebSocketClient } from '@core/websocketclient/WebSocketClient.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { EventCallback, GlobalEventCallback, SnapshotRequestOptions, SnapshotResponseEnvelope, WaitForConnectionOptions } from '@core/websocketclient/types.ts';

let websocketClientInstance: WebSocketClient | null = null;
const getWebSocketClient = (): WebSocketClient => {
    if (!websocketClientInstance) {
        websocketClientInstance = new WebSocketClient();
    }
    return websocketClientInstance;
};
const destroyWebSocketClient = (): void => {
    if (websocketClientInstance) {
        websocketClientInstance.destroy();
        websocketClientInstance = null;
    }
};
const requestWebSocketSnapshot = (resourceName: string, parameters: JsonObject | null = null, options: SnapshotRequestOptions = {}): Promise<SnapshotResponseEnvelope> => getWebSocketClient().requestSnapshot(resourceName, parameters, options);

const subscribeWebSocketEvent = (eventType: string, callback: EventCallback): (() => void) => getWebSocketClient().subscribe(eventType, callback);

const subscribeAllWebSocketEvents = (callback: GlobalEventCallback): (() => void) => getWebSocketClient().subscribeAll(callback);

const connectWebSocket = (): void => {
    getWebSocketClient().connect();
};

const waitForWebSocketConnection = (timeoutMs: number = 15000, options: WaitForConnectionOptions = {}): Promise<void> => getWebSocketClient().waitForConnection(timeoutMs, options);

const sendWebSocketMessage = (payload: JsonObject, options: { waitForConnection?: boolean; timeoutMs?: number; signal?: AbortSignal } = {}): Promise<void> => getWebSocketClient().sendMessage(payload, options);

export { WebSocketClient, connectWebSocket, getWebSocketClient, requestWebSocketSnapshot, sendWebSocketMessage, subscribeAllWebSocketEvents, subscribeWebSocketEvent, waitForWebSocketConnection, destroyWebSocketClient, CONNECTION_STATES, SnapshotError, SnapshotProtocolError };
