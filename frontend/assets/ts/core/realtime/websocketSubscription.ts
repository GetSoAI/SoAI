/* SoAI - WebSocket event subscription lifecycle helper [frontend/assets/ts/core/realtime/websocketSubscription.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { runCleanup } from '@core/lifecycle/cleanup.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isThenable } from '@core/typeGuards.ts';
import { connectWebSocket, subscribeWebSocketEvent } from '@core/websocketclient/service.ts';

interface WebSocketEventSubscriptionOptions {
    label: string;
    eventType: string;
    handler: (payload: JsonValue) => void | Promise<void>;
    signal?: AbortSignal | null | undefined;
}

const isSignalAborted = (signal: AbortSignal | null | undefined): boolean => signal?.aborted === true;

const subscribeManagedWebSocketEvent = (options: WebSocketEventSubscriptionOptions): (() => void) => {
    const signal = options.signal ?? null;
    if (isSignalAborted(signal)) {
        return (): void => {};
    }
    connectWebSocket();
    let unsubscribe: (() => void) | null = subscribeWebSocketEvent(options.eventType, (payload): void => {
        try {
            const result = options.handler(payload);
            if (isThenable(result)) {
                void Promise.resolve(result).catch((error) => {
                    errorHandler.warn(options.label, 'WebSocket event handler failed', ensureError(error));
                });
            }
        } catch (error) {
            errorHandler.warn(options.label, 'WebSocket event handler failed', ensureError(error));
        }
    });
    const cleanupSubscription = (): void => {
        const dispose = unsubscribe;
        unsubscribe = null;
        runCleanup(dispose, (runtimeError) => {
            errorHandler.warn(options.label, 'WebSocket event cleanup failed', runtimeError);
        });
    };
    const cleanup = (): void => {
        signal?.removeEventListener('abort', cleanupSubscription);
        cleanupSubscription();
    };
    signal?.addEventListener('abort', cleanupSubscription, { once: true });
    if (isSignalAborted(signal)) {
        cleanup();
    }
    return cleanup;
};

export { subscribeManagedWebSocketEvent };
export type { WebSocketEventSubscriptionOptions };
