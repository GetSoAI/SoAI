/* SoAI - Shared subscription manager actions [frontend/assets/ts/core/subscriptionmanager/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureStreamManagerReady } from '@core/realtime/streammanager/readiness.ts';
import { createAbortError, isAbortError } from '@core/errors/abort.ts';
import { normalizeUnsubscribe } from '@core/subscriptionmanager/subscriptionExecution.ts';
import { isFunction } from '@core/typeGuards.ts';
import { type ResourceSubscriptionHandler, type SubscriptionHealth, type SubscriptionHandler, type UnsubscribeEntry, type UnsubscribeFunction, type StreamManagerInterface, type HealthStatus, type PendingSubscriptionStart } from '@core/subscriptionmanager/contracts.ts';

interface SubscribeActionContext {
    clearExisting: (key: string) => void;
    incrementVersion: () => number;
    addHealth: (key: string, health: SubscriptionHealth) => void;
    resolveStreamManager: () => StreamManagerInterface;
    setStreamManager: (streamManager: StreamManagerInterface) => void;
    ensureTimers: () => void;
    putSubscription: (key: string, unsubscribe: UnsubscribeEntry) => void;
    beginResourceStart: (key: string, health: SubscriptionHealth) => Promise<void>;
    logDebug: (message: string, error?: Error) => void;
}

interface EnsureReadyActionContext {
    getHealth: () => Map<string, SubscriptionHealth>;
    getSubscriptions: () => Map<string, UnsubscribeEntry>;
    resolveStreamManager: () => Promise<StreamManagerInterface>;
    ensureResourceStarted: (key: string, health: SubscriptionHealth, options?: { signal?: AbortSignal | undefined }) => Promise<void>;
    delay: (ms: number) => Promise<void>;
    logDebug: (message: string, error?: Error) => void;
}

interface DestroyActionContext {
    subscriptions: Map<string, UnsubscribeEntry>;
    health: Map<string, SubscriptionHealth>;
    wsSubscriptions: Map<string, UnsubscribeFunction>;
    pendingStarts: Map<string, PendingSubscriptionStart>;
    timers: { cleanup?: () => void } | null;
    clearTimers: () => void;
    finalizeSubscription: (entry: UnsubscribeEntry | undefined) => void;
    finalizeWebSocket: (unsubscribe: UnsubscribeFunction | undefined) => void;
    clearStreamManager: () => void;
}

const recordDelivery = (health: SubscriptionHealth, context: { initial: boolean }, resourceReady: boolean): void => {
    health.active = true;
    health.errors = 0;
    if (context.initial) {
        health.readyChecked = true;
        health.resourceStarted = resourceReady;
    }
};

const createWrappedStateHandler = (health: SubscriptionHealth, capturedVersion: number, handler: ResourceSubscriptionHandler): ResourceSubscriptionHandler => {
    return (snapshot, context): void => {
        if (health.version !== capturedVersion) {
            return;
        }
        recordDelivery(health, context, snapshot.status === 'ready');
        handler(snapshot, context);
    };
};

const createWrappedValueHandler = (health: SubscriptionHealth, capturedVersion: number, handler: SubscriptionHandler): SubscriptionHandler => {
    return (value, context): void => {
        if (health.version !== capturedVersion) return;
        recordDelivery(health, context, true);
        handler(value, context);
    };
};

type ResourceSubscriptionFactory = (manager: StreamManagerInterface, health: SubscriptionHealth, capturedVersion: number) => UnsubscribeEntry;

const subscribeToResource = (context: SubscribeActionContext, key: string, subscribe: ResourceSubscriptionFactory): (() => void) => {
    if (!key || !isFunction(subscribe)) {
        throw new Error(`Invalid subscription: ${key}`);
    }

    context.clearExisting(key);

    const capturedVersion = context.incrementVersion();
    const health = {
        active: false,
        errors: 0,
        readyChecked: false,
        resourceStarted: false,
        version: capturedVersion
    };
    context.addHealth(key, health);

    const manager = context.resolveStreamManager();
    context.setStreamManager(manager);
    context.ensureTimers();

    const unsubscribeResult = subscribe(manager, health, capturedVersion);
    const unsubscribe = normalizeUnsubscribe(manager.subscriptions, unsubscribeResult);
    context.putSubscription(key, unsubscribe);

    const startPromise = context.beginResourceStart(key, health);
    if (isFunction(startPromise.then)) {
        startPromise.catch((error) => {
            if (isAbortError(error)) {
                return;
            }
            context.logDebug('Start promise rejected', error);
        });
    }

    return () => context.clearExisting(key);
};

interface EnsureReadyOptions {
    signal?: AbortSignal;
}

const ensureManagerReady = async (context: EnsureReadyActionContext, options: EnsureReadyOptions = {}): Promise<void> => {
    const { signal } = options;
    if (signal?.aborted) {
        return;
    }
    await context.resolveStreamManager();
    if (signal?.aborted) {
        return;
    }

    const pending: Array<{ key: string; health: SubscriptionHealth }> = [];
    for (const [key, health] of context.getHealth().entries()) {
        const alreadySubscribed = context.getSubscriptions().get(key);
        if (health.active || health.errors >= 3 || alreadySubscribed || health.readyChecked) {
            continue;
        }
        pending.push({ key, health });
    }

    if (pending.length === 0) {
        return;
    }

    const tasks = pending.map(({ key, health }) => context.ensureResourceStarted(key, health, { signal }));

    if (signal) {
        let onAbortHandler: (() => void) | null = null;
        const abortPromise = new Promise<void>((_unusedValue, reject) => {
            const onAbort = (): void => reject(createAbortError('Subscription readiness aborted'));
            if (signal.aborted) {
                onAbort();
                return;
            }
            onAbortHandler = onAbort;
            signal.addEventListener('abort', onAbort, { once: true });
        });
        try {
            await Promise.race([Promise.all(tasks), abortPromise]);
        } finally {
            if (onAbortHandler) {
                signal.removeEventListener('abort', onAbortHandler);
            }
        }
    } else {
        await Promise.all(tasks);
    }
};

const verifyManagerReadiness = async (context: Pick<EnsureReadyActionContext, 'getHealth' | 'resolveStreamManager' | 'delay' | 'logDebug'>): Promise<void> => {
    const health = context.getHealth();
    if (health.size === 0) {
        return;
    }

    const manager = await context.resolveStreamManager();
    await ensureStreamManagerReady(manager.resources, { allowDiscovery: true });

    const maxWaitTime = 3000;
    const checkInterval = 50;
    const deadline = performance.now() + maxWaitTime;

    while (performance.now() < deadline) {
        const pending = Array.from(health.entries()).filter(([, entryHealth]) => !entryHealth.active && entryHealth.errors < 3);

        if (pending.length === 0) {
            return;
        }

        const hasStartingResources = pending.some(([, entryHealth]) => entryHealth.resourceStarted && entryHealth.errors === 0);
        if (!hasStartingResources) {
            break;
        }

        await context.delay(checkInterval);
    }

    const stillUnhealthy = Array.from(health.entries()).filter(([, entryHealth]) => !entryHealth.active && entryHealth.errors < 3);

    if (stillUnhealthy.length > 0) {
        const unhealthyKeys = stillUnhealthy.map(([key]) => key);
        context.logDebug(`Subscriptions not ready: ${unhealthyKeys.join(', ')}`);
    }
};

const getHealthStatus = (health: Map<string, SubscriptionHealth>): HealthStatus[] => {
    return Array.from(health.entries()).map(([key, entry]) => ({
        key,
        active: entry.active,
        errors: entry.errors
    }));
};

const destroyManager = (context: DestroyActionContext): void => {
    context.subscriptions.forEach((unsubscribe: UnsubscribeEntry | undefined) => {
        context.finalizeSubscription(unsubscribe);
    });
    context.subscriptions.clear();
    context.health.clear();
    context.wsSubscriptions.forEach((unsubscribe: UnsubscribeFunction | undefined) => {
        context.finalizeWebSocket(unsubscribe);
    });
    context.wsSubscriptions.clear();
    context.pendingStarts.forEach((entry) => {
        entry.controller.abort();
    });
    if (context.timers?.cleanup) {
        context.timers.cleanup();
    }
    context.clearTimers();
    context.pendingStarts.clear();
    context.clearStreamManager();
};

export { createWrappedStateHandler, createWrappedValueHandler, destroyManager, ensureManagerReady, getHealthStatus, subscribeToResource, verifyManagerReadiness };
export type { ResourceSubscriptionFactory, SubscribeActionContext };
