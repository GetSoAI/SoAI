/* SoAI - Shared frontend WebSocket client connection wait [frontend/assets/ts/core/websocketclient/connectionWait.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError } from '@core/errors/abort.ts';

interface WaitForConnectionRuntime {
    timeoutMs: number;
    signal?: AbortSignal | undefined;
    isConnected: () => boolean;
    isDestroyed: () => boolean;
    subscribeConnected: (listener: () => void) => () => void;
    subscribeClosed: (listener: (error: Error) => void) => () => void;
}

const waitForWebSocketConnection = (options: WaitForConnectionRuntime): Promise<void> => {
    if (options.isConnected()) {
        return Promise.resolve();
    }
    if (options.isDestroyed()) {
        return Promise.reject(new Error('WebSocketClient has been destroyed'));
    }
    if (options.signal?.aborted) {
        return Promise.reject(createAbortError());
    }
    return new Promise((resolve, reject) => {
        let settled = false;
        let unsubscribeConnected: (() => void) | null = null;
        let unsubscribeClosed: (() => void) | null = null;
        const timeout = setTimeout(() => {
            settleReject(new Error('WebSocket connection timeout'));
        }, options.timeoutMs);

        const cleanup = (): void => {
            clearTimeout(timeout);
            if (unsubscribeConnected) {
                unsubscribeConnected();
                unsubscribeConnected = null;
            }
            if (unsubscribeClosed) {
                unsubscribeClosed();
                unsubscribeClosed = null;
            }
            options.signal?.removeEventListener('abort', onAbort);
        };

        const settleResolve = (): void => {
            if (settled) return;
            settled = true;
            cleanup();
            resolve();
        };

        const settleReject = (error: Error): void => {
            if (settled) return;
            settled = true;
            cleanup();
            reject(error);
        };

        const onAbort = (): void => {
            settleReject(createAbortError());
        };

        options.signal?.addEventListener('abort', onAbort, { once: true });
        const connectedCleanup = options.subscribeConnected(settleResolve);
        if (settled) connectedCleanup();
        else unsubscribeConnected = connectedCleanup;
        const closedCleanup = options.subscribeClosed(settleReject);
        if (settled) closedCleanup();
        else unsubscribeClosed = closedCleanup;
        if (options.signal?.aborted) {
            onAbort();
        } else if (options.isConnected()) {
            settleResolve();
        } else if (options.isDestroyed()) {
            settleReject(new Error('WebSocketClient has been destroyed'));
        }
    });
};

export { waitForWebSocketConnection };
