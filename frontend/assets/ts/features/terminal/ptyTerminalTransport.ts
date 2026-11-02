/* SoAI - Connection-owned terminal PTY WebSocket commands [frontend/assets/ts/features/terminal/ptyTerminalTransport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { TIMEOUTS } from '@core/constants.ts';
import { i18n } from '@core/i18n/index.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { withTimeout } from '@core/primitives/withTimeout.ts';
import type { PtyAcquisitionIdentity } from '@core/realtime/eventcontracts/terminalContracts.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';
import { isCurrentWebSocketClient } from '@core/websocketclient/service.ts';
import type { WebSocketClient } from '@core/websocketclient/WebSocketClient.ts';
import { WebSocketReconnectInterruptionError } from '@core/websocketclient/connectionInterruption.ts';
import { encodeTerminalInput } from '@features/terminal/ptyTerminalCodec.ts';

interface PtyTerminalConnection {
    readonly client: Pick<WebSocketClient, 'connectionEpoch' | 'isConnected' | 'sendMessage' | 'subscribe' | 'terminalRuntimeId'>;
    readonly connectionEpoch: number;
}

interface PtyTerminalAcquisition extends PtyTerminalConnection, PtyAcquisitionIdentity {
    readonly authEpoch: number;
}

const waitForPtyRuntime = async (connection: PtyTerminalConnection, signal?: AbortSignal): Promise<string> => {
    throwIfAborted(signal);
    if (connection.client.terminalRuntimeId) return connection.client.terminalRuntimeId;
    const completion = createDeferred<string>();
    const cleanup = subscribeManagedWebSocketContracts({
        label: 'PtyRuntime',
        subscribe: (type, handler) => connection.client.subscribe(type, handler),
        events: [
            createWebSocketContractBinding({
                contract: WEBSOCKET_EVENT_CONTRACTS.terminal.runtime,
                handler: (runtimeId, context) => {
                    if (context.connectionEpoch !== connection.connectionEpoch || !isCurrentWebSocketClient(connection.client)) return;
                    if (runtimeId) completion.resolve(runtimeId);
                    else completion.reject(new Error(i18n.t('terminal.errors.recoveryUnavailable')));
                },
                onInvalidPayload: completion.reject
            })
        ]
    });
    try {
        return await withTimeout(signal ? raceWithAbortSignal(completion.promise, signal) : completion.promise, { timeoutMs: TIMEOUTS.API_REQUEST, timeoutMessage: i18n.t('terminal.errors.recoveryUnavailable') });
    } finally {
        cleanup();
    }
};

const sendPtyReleaseMessage = (connection: PtyTerminalConnection, identity: PtyAcquisitionIdentity): Promise<void> => sendPtyMessage(connection, { type: WEBSOCKET_MESSAGE_TYPES.PTY_RELEASE, 'runtime_id': identity.runtimeId, 'acquisition_id': identity.acquisitionId });

const sendPtyMessage = async (connection: PtyTerminalConnection, payload: JsonObject, signal?: AbortSignal): Promise<void> => {
    throwIfAborted(signal);
    const requireConnection = (): void => {
        if (!isCurrentWebSocketClient(connection.client) || !connection.client.isConnected() || connection.client.connectionEpoch !== connection.connectionEpoch) throw new WebSocketReconnectInterruptionError('PTY command connection is no longer available');
    };
    requireConnection();
    await connection.client.sendMessage(payload, { waitForConnection: false, ...(signal ? { signal } : {}) });
    requireConnection();
};

const sendPtyConnectMessage = (connection: PtyTerminalAcquisition, cols: number, rows: number, shell: string | null, signal?: AbortSignal): Promise<void> => sendPtyMessage(connection, { type: WEBSOCKET_MESSAGE_TYPES.PTY_CONNECT, cols, rows, shell, 'runtime_id': connection.runtimeId, 'acquisition_id': connection.acquisitionId }, signal);

const sendPtyDisconnectMessage = (connection: PtyTerminalConnection): Promise<void> => sendPtyMessage(connection, { type: WEBSOCKET_MESSAGE_TYPES.PTY_DISCONNECT });

const sendPtyInputMessage = (connection: PtyTerminalConnection, data: string): Promise<void> => sendPtyMessage(connection, { type: WEBSOCKET_MESSAGE_TYPES.PTY_INPUT, data: encodeTerminalInput(data) });

const sendPtyResizeMessage = (connection: PtyTerminalConnection, cols: number, rows: number): Promise<void> => sendPtyMessage(connection, { type: WEBSOCKET_MESSAGE_TYPES.PTY_RESIZE, cols, rows });

export { sendPtyReleaseMessage, waitForPtyRuntime, sendPtyConnectMessage, sendPtyDisconnectMessage, sendPtyInputMessage, sendPtyResizeMessage };
export type { PtyTerminalAcquisition, PtyTerminalConnection };
