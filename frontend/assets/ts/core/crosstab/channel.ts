/* SoAI - Shared crosstab channel [frontend/assets/ts/core/crosstab/channel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getBroadcastChannelCtor } from '@core/environment/public.ts';
import type { ErrorHandler } from '@core/state/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

type ChannelListener = (message: JsonValue | null | undefined) => void;
type CrossTabPublishOutcome = 'published' | 'queued';
type CrossTabMessage = JsonValue | null | undefined;

interface CrossTabTransport {
    onmessage: ((event: MessageEvent) => void) | null;
    postMessage(message: CrossTabMessage): void;
    close(): void;
}

type CrossTabTransportFactory = (channelId: string) => CrossTabTransport;

interface CrossTabChannel {
    publish(message: CrossTabMessage): CrossTabPublishOutcome;
    subscribe(listener: ChannelListener): () => void;
    close(): void;
}

const createBrowserCrossTabTransport = (channelId: string): CrossTabTransport => {
    const BroadcastChannelCtor = getBroadcastChannelCtor();
    return new BroadcastChannelCtor(channelId);
};

const createCrossTabChannel = (channelId: string, errorHandler: ErrorHandler, createTransport: CrossTabTransportFactory = createBrowserCrossTabTransport): CrossTabChannel => {
    if (!channelId) {
        throw new Error('Cross-tab channel requires an identifier');
    }
    const channel = createTransport(channelId);
    const listeners = new Set<ChannelListener>();
    let pendingPublication: { message: CrossTabMessage } | null = null;
    let retryHandle: ReturnType<typeof setTimeout> | null = null;
    let retryDelayMs = 250;
    let degraded = false;
    let closed = false;

    function clearRetry(): void {
        if (retryHandle === null) return;
        clearTimeout(retryHandle);
        retryHandle = null;
    }

    function scheduleRetry(publication: { message: CrossTabMessage }): void {
        if (retryHandle !== null) return;
        const delayMs = retryDelayMs;
        retryDelayMs = Math.min(retryDelayMs * 2, 5000);
        retryHandle = setTimeout(() => {
            retryHandle = null;
            attemptPublish(publication.message);
        }, delayMs);
    }

    function attemptPublish(message: CrossTabMessage): CrossTabPublishOutcome {
        if (closed) throw new Error(`Cross-tab channel "${channelId}" is closed`);
        try {
            channel.postMessage(message);
            pendingPublication = null;
            clearRetry();
            retryDelayMs = 250;
            if (degraded) errorHandler.info?.('CrossTabChannel', 'Queued publication recovered', { channelId });
            degraded = false;
            return 'published';
        } catch (error) {
            const publication = pendingPublication ?? { message };
            publication.message = message;
            pendingPublication = publication;
            if (!degraded) errorHandler.warn?.('CrossTabChannel', 'Publication queued after transport failure', ensureError(error));
            degraded = true;
            scheduleRetry(publication);
            return 'queued';
        }
    }

    channel.onmessage = (event: MessageEvent) => {
        const payload = event.data;
        if (payload === undefined) {
            return;
        }
        const snapshot = [...listeners];
        snapshot.forEach((listener) => {
            try {
                listener(payload);
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.debug?.('CrossTabChannel', 'Listener failed', runtimeError);
            }
        });
    };

    return Object.freeze({
        publish(message: CrossTabMessage): CrossTabPublishOutcome {
            return attemptPublish(message);
        },
        subscribe(listener: ChannelListener): () => void {
            if (!isFunction(listener)) {
                throw new TypeError('Cross-tab channel subscription requires a listener');
            }
            if (closed) throw new Error(`Cross-tab channel "${channelId}" is closed`);
            listeners.add(listener);
            return () => {
                listeners.delete(listener);
            };
        },
        close(): void {
            if (closed) return;
            closed = true;
            clearRetry();
            pendingPublication = null;
            listeners.clear();
            channel.close();
        }
    });
};

export { createCrossTabChannel };
export type { CrossTabChannel, CrossTabMessage, CrossTabPublishOutcome, CrossTabTransport, CrossTabTransportFactory, ChannelListener };
