/* SoAI - Shared subscription manager effects [frontend/assets/ts/core/subscriptionmanager/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createAbortSignalScope, raceWithAbortSignal } from '@core/errors/abort.ts';
import { getStreamRuntime } from '@core/realtime/streammanager/public.ts';
import { isStreamManagerInterface, validateStreamManager } from '@core/subscriptionmanager/internalContracts.ts';
import { type PendingSubscriptionStart, type SubscriptionHealth, type StreamManagerInterface } from '@core/subscriptionmanager/contracts.ts';
import { type SubscriptionManagerState } from '@core/subscriptionmanager/state.ts';

interface StartResourceCallbacks {
    onError: (key: string, health: SubscriptionHealth, error: Error) => void;
}

const resolveStreamManager = (state: SubscriptionManagerState): StreamManagerInterface => {
    if (state.streamManager) {
        return state.streamManager;
    }
    const manager = validateStreamManager(getStreamRuntime());
    state.streamManager = manager;
    return manager;
};

const resolveUnsubscribeManager = (state: SubscriptionManagerState): { unsubscribe?: (id: string) => void } => {
    if (state.streamManager) {
        return state.streamManager.subscriptions;
    }
    const candidate = getStreamRuntime();
    if (isStreamManagerInterface(candidate)) return candidate.subscriptions;
    return {};
};

const getStreamManagerForSubscription = (state: SubscriptionManagerState): Promise<StreamManagerInterface> => {
    return Promise.resolve(resolveStreamManager(state));
};

const ensureTimers = (state: SubscriptionManagerState): void => {
    if (state.timers) {
        return;
    }
    state.timers = new ResourceTracker();
};

const delay = (state: SubscriptionManagerState, ms: number): Promise<void> => {
    ensureTimers(state);
    return new Promise((resolve) => {
        if (!state.timers?.setTimeout) {
            setTimeout(resolve, ms);
            return;
        }
        state.timers.setTimeout(resolve, ms);
    });
};

const startWithManager = async (key: string, health: SubscriptionHealth, manager: StreamManagerInterface, signal: AbortSignal, onError: StartResourceCallbacks['onError']): Promise<void> => {
    await manager.resources.ensureReady({ allowDiscovery: true, throwOnError: false, signal });
    const result = await manager.resources.ensureResourceStarted(key, {
        allowDiscovery: true,
        throwOnError: false,
        signal
    });
    if (result === null) {
        onError(key, health, new Error('Resource start returned null'));
        return;
    }

    health.readyChecked = true;
    health.resourceStarted = true;
};

const ensureResourceStarted = (state: SubscriptionManagerState, key: string, health: SubscriptionHealth, onError: StartResourceCallbacks['onError'], options: { signal?: AbortSignal | undefined } = {}): Promise<void> => {
    if (!state.pendingStarts.has(key)) {
        const manager = resolveStreamManager(state);
        const controller = new AbortController();
        const signalScope = createAbortSignalScope([controller.signal, options.signal]);
        let pendingStart: PendingSubscriptionStart | null = null;
        const startTask = startWithManager(key, health, manager, signalScope.signal, onError).finally(() => {
            signalScope.cleanup();
            if (pendingStart && state.pendingStarts.get(key) === pendingStart) {
                state.pendingStarts.delete(key);
            }
        });
        pendingStart = { controller, promise: startTask };
        state.pendingStarts.set(key, pendingStart);
    }

    const startTask = state.pendingStarts.get(key);
    if (!startTask) {
        throw new Error('Subscription start task could not be initialized');
    }

    return options.signal ? raceWithAbortSignal(startTask.promise, options.signal) : startTask.promise;
};

export { delay, ensureResourceStarted, getStreamManagerForSubscription, resolveStreamManager, resolveUnsubscribeManager, ensureTimers };
