/* SoAI - Metrics page realtime [frontend/assets/ts/pages/metrics/realtime/metricsPageRealtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { scheduleRequiredRender } from '@core/runtime/animationFrames.ts';
import { runCleanupCallbacks } from '@core/lifecycle/cleanup.ts';
import { disposeResourceStreamSubscriptions, subscribeResourceStateStreamBatch, type ResourceStreamSubscription } from '@core/realtime/resourceSubscriptions.ts';
import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { MetricsData } from '@pages/metrics/types.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';

interface MetricsStreamHost extends PageResourcesOwnerHost {
    subscribeToData: (resource: string, handler: (value: JsonValue | null) => void) => () => void;
    ensureDataSubscriptions: (options: { signal?: AbortSignal }) => Promise<void>;
    requestAnimationFrame: (callback: FrameRequestCallback) => number;
    cancelAnimationFrame: (frameId: number) => void;
    isActive: () => boolean;
    processMetricsUpdate: (data: MetricsData) => void;
    refreshMetricsDisplays: () => void;
    processPluginsUpdate: (data: readonly JsonValue[]) => void;
    setMetricsDisposer: (disposer: (() => void) | null) => void;
    setPluginsDisposer: (disposer: (() => void) | null) => void;
    disposeMetricsSubscription: () => void;
    disposePluginsSubscription: () => void;
    metricsStreamId: string;
    pluginsStreamId: string;
}

const isMetricsData = (value: JsonValue | null): value is MetricsData => {
    return isJsonObject(value);
};

const disposeMetricsStreamSubscriptions = (host: MetricsStreamHost, metricsSubscription: ResourceStreamSubscription, pluginsSubscription: ResourceStreamSubscription, registrations: { metrics: boolean; plugins: boolean }): void => {
    let firstError: Error | null = null;
    runCleanupCallbacks([registrations.metrics ? () => host.disposeMetricsSubscription() : metricsSubscription.dispose, registrations.plugins ? () => host.disposePluginsSubscription() : pluginsSubscription.dispose], (runtimeError) => {
        firstError = firstError ?? runtimeError;
    });
    if (firstError) {
        throw firstError;
    }
};

const initializeMetricsStream = async (host: MetricsStreamHost, signal: AbortSignal): Promise<void> => {
    host.disposeMetricsSubscription();
    host.disposePluginsSubscription();
    let cancelPendingRender: (() => void) | null = null;
    const renderCleanupController = new AbortController();
    const isCurrent = (): boolean => !signal.aborted && !renderCleanupController.signal.aborted && host.isActive();
    const cancelPendingMetricsRender = (): void => {
        cancelPendingRender?.();
        cancelPendingRender = null;
    };
    const disposePendingMetricsRender = (): void => {
        renderCleanupController.abort();
        cancelPendingMetricsRender();
    };
    const flushMetricsDisplays = (): void => {
        cancelPendingRender = null;
        if (!isCurrent()) {
            return;
        }
        host.refreshMetricsDisplays();
    };
    const queueMetricsUpdate = (data: MetricsData): void => {
        host.processMetricsUpdate(data);
        if (!isCurrent()) {
            return;
        }
        if (cancelPendingRender !== null) {
            return;
        }
        cancelPendingRender = scheduleRequiredRender(flushMetricsDisplays, { requestAnimationFrame: (callback) => host.requestAnimationFrame(callback), cancelAnimationFrame: (identifier) => host.cancelAnimationFrame(identifier) });
    };
    signal.addEventListener('abort', cancelPendingMetricsRender, { once: true, signal: renderCleanupController.signal });

    let subscriptions: ResourceStreamSubscription[];
    try {
        subscriptions = subscribeResourceStateStreamBatch({
            label: 'Metrics realtime',
            subscribeToData: (resource, handler) => host.subscribeToData(resource, handler),
            bindings: [
                {
                    resource: host.metricsStreamId,
                    handler: (value: JsonValue | null): void => {
                        if (!isCurrent()) return;
                        if (!isMetricsData(value)) {
                            throw new Error('Metrics realtime payload must be an object');
                        }
                        queueMetricsUpdate(value);
                    }
                },
                {
                    resource: host.pluginsStreamId,
                    handler: (value: JsonValue | null): void => {
                        if (!isCurrent()) return;
                        if (!isJsonArray(value)) {
                            throw new Error('Plugins realtime payload must be an array');
                        }
                        host.processPluginsUpdate(value);
                    }
                }
            ]
        });
    } catch (error) {
        disposePendingMetricsRender();
        throw ensureError(error);
    }
    const metricsSubscription = subscriptions[0];
    const pluginsSubscription = subscriptions[1];
    if (!metricsSubscription || !pluginsSubscription) {
        const initializationError = new Error('Metrics realtime subscriptions were not initialized');
        try {
            disposeResourceStreamSubscriptions(subscriptions);
        } catch (cleanupError) {
            throw new AggregateError([initializationError, ensureError(cleanupError)], 'Metrics realtime subscription initialization failed and cleanup also failed');
        }
        throw initializationError;
    }
    const metricsSubscriptionWithRenderCleanup: ResourceStreamSubscription = {
        dispose: (): void => {
            disposePendingMetricsRender();
            metricsSubscription.dispose();
        }
    };

    let metricsDisposerRegistered = false;
    let pluginsDisposerRegistered = false;
    try {
        host.setMetricsDisposer(metricsSubscriptionWithRenderCleanup.dispose);
        metricsDisposerRegistered = true;
        host.setPluginsDisposer(pluginsSubscription.dispose);
        pluginsDisposerRegistered = true;
        await host.ensureDataSubscriptions({ signal });
    } catch (error) {
        try {
            disposeMetricsStreamSubscriptions(host, metricsSubscriptionWithRenderCleanup, pluginsSubscription, { metrics: metricsDisposerRegistered, plugins: pluginsDisposerRegistered });
        } catch (cleanupError) {
            throw new AggregateError([ensureError(error), ensureError(cleanupError)], 'Metrics realtime initialization failed and cleanup also failed');
        }
        throw ensureError(error);
    }

    if (!host.isActive()) {
        disposeMetricsStreamSubscriptions(host, metricsSubscriptionWithRenderCleanup, pluginsSubscription, { metrics: true, plugins: true });
        return;
    }

    try {
        host.pageResources.track(metricsSubscriptionWithRenderCleanup.dispose, () => host.disposeMetricsSubscription());
        host.pageResources.track(pluginsSubscription.dispose, () => host.disposePluginsSubscription());
    } catch (error) {
        try {
            disposeMetricsStreamSubscriptions(host, metricsSubscriptionWithRenderCleanup, pluginsSubscription, { metrics: true, plugins: true });
        } catch (cleanupError) {
            throw new AggregateError([ensureError(error), ensureError(cleanupError)], 'Metrics realtime tracking failed and cleanup also failed');
        }
        throw ensureError(error);
    }
};

export { initializeMetricsStream };
export type { MetricsStreamHost };
