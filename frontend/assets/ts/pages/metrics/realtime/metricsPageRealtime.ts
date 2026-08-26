/* SoAI - Metrics page realtime [frontend/assets/ts/pages/metrics/realtime/metricsPageRealtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
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
    let pendingMetrics: MetricsData | null = null;
    let pendingFrame: number | null = null;
    const frameCleanupController = new AbortController();
    const cancelPendingMetricsFrame = (): void => {
        if (pendingFrame !== null) {
            host.cancelAnimationFrame(pendingFrame);
            pendingFrame = null;
        }
        pendingMetrics = null;
    };
    const disposePendingMetricsFrame = (): void => {
        frameCleanupController.abort();
        cancelPendingMetricsFrame();
    };
    const flushPendingMetrics = (): void => {
        pendingFrame = null;
        const data = pendingMetrics;
        pendingMetrics = null;
        if (!data || signal.aborted || !host.isActive()) {
            return;
        }
        host.processMetricsUpdate(data);
    };
    const queueMetricsUpdate = (data: MetricsData): void => {
        if (signal.aborted || !host.isActive()) {
            return;
        }
        pendingMetrics = data;
        if (pendingFrame !== null) {
            return;
        }
        pendingFrame = host.requestAnimationFrame(flushPendingMetrics);
    };
    signal.addEventListener('abort', cancelPendingMetricsFrame, { once: true, signal: frameCleanupController.signal });

    const subscriptions = subscribeResourceStateStreamBatch({
        label: 'Metrics realtime',
        subscribeToData: (resource, handler) => host.subscribeToData(resource, handler),
        bindings: [
            {
                resource: host.metricsStreamId,
                handler: (value: JsonValue | null): void => {
                    if (!isMetricsData(value)) {
                        throw new Error('Metrics realtime payload must be an object');
                    }
                    queueMetricsUpdate(value);
                }
            },
            {
                resource: host.pluginsStreamId,
                handler: (value: JsonValue | null): void => {
                    if (!isJsonArray(value)) {
                        throw new Error('Plugins realtime payload must be an array');
                    }
                    host.processPluginsUpdate(value);
                }
            }
        ]
    });
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
    const metricsSubscriptionWithFrameCleanup: ResourceStreamSubscription = {
        dispose: (): void => {
            disposePendingMetricsFrame();
            metricsSubscription.dispose();
        }
    };

    let metricsDisposerRegistered = false;
    let pluginsDisposerRegistered = false;
    try {
        host.setMetricsDisposer(metricsSubscriptionWithFrameCleanup.dispose);
        metricsDisposerRegistered = true;
        host.setPluginsDisposer(pluginsSubscription.dispose);
        pluginsDisposerRegistered = true;
        await host.ensureDataSubscriptions({ signal });
    } catch (error) {
        try {
            disposeMetricsStreamSubscriptions(host, metricsSubscriptionWithFrameCleanup, pluginsSubscription, { metrics: metricsDisposerRegistered, plugins: pluginsDisposerRegistered });
        } catch (cleanupError) {
            throw new AggregateError([ensureError(error), ensureError(cleanupError)], 'Metrics realtime initialization failed and cleanup also failed');
        }
        throw ensureError(error);
    }

    if (!host.isActive()) {
        disposeMetricsStreamSubscriptions(host, metricsSubscriptionWithFrameCleanup, pluginsSubscription, { metrics: true, plugins: true });
        return;
    }

    try {
        host.pageResources.track(metricsSubscriptionWithFrameCleanup.dispose, () => host.disposeMetricsSubscription());
        host.pageResources.track(pluginsSubscription.dispose, () => host.disposePluginsSubscription());
    } catch (error) {
        try {
            disposeMetricsStreamSubscriptions(host, metricsSubscriptionWithFrameCleanup, pluginsSubscription, { metrics: true, plugins: true });
        } catch (cleanupError) {
            throw new AggregateError([ensureError(error), ensureError(cleanupError)], 'Metrics realtime tracking failed and cleanup also failed');
        }
        throw ensureError(error);
    }
};

export { initializeMetricsStream };
export type { MetricsStreamHost };
