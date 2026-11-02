/* SoAI - Confirmed acquisition release and reconnect recovery [frontend/assets/ts/features/terminal/ptyTerminalDisconnectQueue.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getAuthManager } from '@core/auth/public.ts';
import { TIMEOUTS } from '@core/constants.ts';
import { i18n } from '@core/i18n/index.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { withTimeout } from '@core/primitives/withTimeout.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createDeferred, type Deferred } from '@core/runtime/deferred.ts';
import { getWebSocketClient, isCurrentWebSocketClient } from '@core/websocketclient/service.ts';
import { sendPtyReleaseMessage, type PtyTerminalAcquisition, type PtyTerminalConnection } from '@features/terminal/ptyTerminalTransport.ts';

interface PendingPtyDisconnect {
    readonly request: PtyTerminalAcquisition;
    readonly completion: Deferred<void>;
    attempt: Promise<Error | null> | null;
    response: Deferred<void> | null;
    failure: Error | null;
    status: 'pending' | 'confirmed' | 'unconfirmed';
    retryRequested: boolean;
}

const pendingDisconnects = new Set<PendingPtyDisconnect>();
let observedClient: PtyTerminalConnection['client'] | null = null;
let cleanupObservers: (() => void) | null = null;
let cleanupAuthentication: (() => void) | null = null;

const releaseUnconfirmed = (): Error => new Error(i18n.t('terminal.errors.releaseUnconfirmed'));

const settleRelease = (pending: PendingPtyDisconnect, failure: Error | null): void => {
    if (pending.status !== 'pending') return;
    pending.status = failure ? 'unconfirmed' : 'confirmed';
    pending.failure = failure;
    pending.retryRequested = false;
    if (failure) {
        pending.response?.reject(failure);
        pending.completion.reject(failure);
    } else {
        pending.response?.resolve();
        pending.completion.resolve();
    }
    pendingDisconnects.delete(pending);
    if (pendingDisconnects.size === 0) {
        cleanupObservers?.();
        cleanupObservers = null;
        observedClient = null;
        cleanupAuthentication?.();
        cleanupAuthentication = null;
    }
};

const reconcilePending = (): void => {
    for (const pending of pendingDisconnects) {
        if (pending.attempt) pending.retryRequested = true;
        else terminateHandledPromise(attemptRelease(pending));
    }
};

const observeRelease = (): void => {
    const client = getWebSocketClient();
    if (observedClient === client || pendingDisconnects.size === 0 || [...pendingDisconnects].every((pending) => pending.request.authEpoch !== getAuthManager().authEpoch)) return;
    cleanupObservers?.();
    observedClient = client;
    cleanupAuthentication ??= getAuthManager().onEpochIntent(() => {
        for (const pending of [...pendingDisconnects]) {
            if (pending.request.authEpoch !== getAuthManager().authEpoch) settleRelease(pending, releaseUnconfirmed());
        }
    });
    cleanupObservers = subscribeManagedWebSocketContracts({
        label: 'PtyTerminalRelease',
        subscribe: (type, handler) => client.subscribe(type, handler),
        events: [
            createWebSocketContractBinding({
                contract: WEBSOCKET_EVENT_CONTRACTS.terminal.released,
                handler: (identity, context) => {
                    if (!isCurrentWebSocketClient(client) || context.connectionEpoch !== client.connectionEpoch) return;
                    for (const pending of pendingDisconnects) {
                        if (pending.request.authEpoch === getAuthManager().authEpoch && identity.acquisitionId === pending.request.acquisitionId && identity.runtimeId === pending.request.runtimeId) settleRelease(pending, null);
                    }
                },
                onInvalidPayload: (error) => {
                    for (const pending of pendingDisconnects) pending.response?.reject(error);
                }
            }),
            createWebSocketContractBinding({
                contract: WEBSOCKET_EVENT_CONTRACTS.terminal.error,
                handler: (error, context) => {
                    if (!isCurrentWebSocketClient(client) || context.connectionEpoch !== client.connectionEpoch) return;
                    for (const pending of pendingDisconnects) {
                        if (error.details?.['acquisition_id'] === pending.request.acquisitionId && error.details['runtime_id'] === pending.request.runtimeId) pending.response?.reject(new Error(`${releaseUnconfirmed().message} ${error.message}`));
                    }
                }
            }),
            createWebSocketContractBinding({
                contract: WEBSOCKET_EVENT_CONTRACTS.terminal.runtime,
                handler: (_payload, context) => {
                    if (isCurrentWebSocketClient(client) && context.connectionEpoch === client.connectionEpoch) reconcilePending();
                }
            }),
            createWebSocketContractBinding({
                contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.disconnected,
                handler: (_payload, context) => {
                    if (!isCurrentWebSocketClient(client) || context.connectionEpoch !== client.connectionEpoch) return;
                    for (const pending of pendingDisconnects) pending.response?.reject(releaseUnconfirmed());
                }
            })
        ]
    });
};

const attemptRelease = (pending: PendingPtyDisconnect): Promise<Error | null> => {
    if (pending.status !== 'pending') return pending.completion.promise.then(() => null, ensureError);
    if (pending.attempt) return pending.attempt;
    observeRelease();
    const completion = createDeferred<Error | null>();
    pending.attempt = completion.promise;
    const response = createDeferred<void>();
    pending.response = response;
    const attempt = async (): Promise<void> => {
        const client = getWebSocketClient();
        if (getAuthManager().authEpoch !== pending.request.authEpoch || !client.isConnected() || client.terminalRuntimeId !== pending.request.runtimeId) throw releaseUnconfirmed();
        const connection = { client, connectionEpoch: client.connectionEpoch };
        const acknowledgement = withTimeout(response.promise, { timeoutMs: TIMEOUTS.API_REQUEST, timeoutMessage: releaseUnconfirmed().message });
        void sendPtyReleaseMessage(connection, pending.request).catch((error) => {
            if (pending.status === 'pending') response.reject(ensureError(error));
        });
        await acknowledgement;
    };
    void attempt().then(
        () => {
            pending.attempt = null;
            pending.response = null;
            completion.resolve(null);
        },
        (error) => {
            pending.attempt = null;
            pending.response = null;
            if (pending.status !== 'pending') completion.resolve(pending.failure);
            else {
                pending.failure = ensureError(error);
                completion.resolve(pending.failure);
                if (pending.retryRequested) {
                    pending.retryRequested = false;
                    terminateHandledPromise(attemptRelease(pending));
                }
            }
        }
    );
    return completion.promise;
};

const queuePtyDisconnect = (request: PtyTerminalAcquisition): Promise<void> => {
    const existing = [...pendingDisconnects].find((pending) => pending.request.acquisitionId === request.acquisitionId && pending.request.runtimeId === request.runtimeId);
    if (existing) {
        terminateHandledPromise(attemptRelease(existing));
        return existing.completion.promise;
    }
    const pending: PendingPtyDisconnect = { request, completion: createDeferred<void>(), attempt: null, response: null, failure: null, status: 'pending', retryRequested: false };
    pendingDisconnects.add(pending);
    if (request.authEpoch !== getAuthManager().authEpoch) {
        settleRelease(pending, releaseUnconfirmed());
        return pending.completion.promise;
    }
    observeRelease();
    terminateHandledPromise(attemptRelease(pending));
    return pending.completion.promise;
};

const settlePendingPtyDisconnects = async (): Promise<void> => {
    observeRelease();
    const pending = [...pendingDisconnects];
    await Promise.all(
        pending.map(async (release) => {
            const failure = await attemptRelease(release);
            if (failure) throw failure;
            await withTimeout(release.completion.promise, { timeoutMs: TIMEOUTS.API_REQUEST, timeoutMessage: (release.failure ?? releaseUnconfirmed()).message });
        })
    );
    if (pendingDisconnects.size === 0) {
        cleanupObservers?.();
        cleanupObservers = null;
        observedClient = null;
        cleanupAuthentication?.();
        cleanupAuthentication = null;
    }
};

export { queuePtyDisconnect, settlePendingPtyDisconnects };
