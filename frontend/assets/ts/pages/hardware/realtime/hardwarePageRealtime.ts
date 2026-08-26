/* SoAI - Hardware page realtime [frontend/assets/ts/pages/hardware/realtime/hardwarePageRealtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildSignalRequestOptions } from '@core/api/requestOptions.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { runCleanupCallbacks } from '@core/lifecycle/cleanup.ts';
import type { LogLevel } from '@core/moduleContext.ts';
import { disposeResourceStreamSubscriptions, subscribeResourceStateStreamBatch, type ResourceStreamSubscription } from '@core/realtime/resourceSubscriptions.ts';
import { HARDWARE_GPU_CAPABILITIES, HARDWARE_GPU_SLOTS, HARDWARE_GPU_SOAIBENCH_RUNS, HARDWARE_PROCESSES } from '@core/realtime/streammanager/resources/ids.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import type { ResourcesInterface } from '@pages/hardware/contracts/contracts.ts';

interface HardwareRealtimeHost {
    realtimeStreamActive: boolean;
    realtimeSubscriptionHandles: Set<() => void>;
    resources?: ResourcesInterface | null;

    resolveStreamManager: (options?: { signal?: AbortSignal | undefined }) => Promise<StreamRuntimeOwners | null>;
    ensureDataSubscriptions: (options?: { signal?: AbortSignal }) => Promise<void>;
    subscribeToData: (resource: string, handler: (value: JsonValue | null) => void) => (() => void) | null;
    trackDisposable: (resource: () => void, onDispose?: () => void) => void;
    hasGrantedAction: (action: string) => boolean;
    hasProcessPanel: () => boolean;

    handleSnapshot: (value: JsonValue | null) => void;
    processMetricsUpdate: (value: JsonValue | null) => void;
    handleGpuCapabilities: (value: JsonValue | null) => void;
    handleSavedGpuSettings: (value: JsonValue | null) => void;
    handleSoAIBenchRunsUpdate: (value: JsonValue | null) => void;
    handleProcessResourceUpdate: (value: JsonValue | null) => void;
}

interface HardwareRealtimeStreams {
    hardwareSnapshotStream: string;
    systemMetricsStream: string;
}

const setupRealtimeSubscriptions = (host: HardwareRealtimeHost, streams: HardwareRealtimeStreams): void => {
    if (host.realtimeStreamActive) {
        return;
    }
    host.realtimeStreamActive = true;

    const subscriptions: Array<[string, (value: JsonValue | null) => void]> = [
        [streams.hardwareSnapshotStream, (value: JsonValue | null) => host.handleSnapshot(value)],
        [streams.systemMetricsStream, (value: JsonValue | null) => host.processMetricsUpdate(value)]
    ];

    if (host.hasGrantedAction('HW_GPU_TUNING')) {
        subscriptions.push([HARDWARE_GPU_CAPABILITIES, (value: JsonValue | null) => host.handleGpuCapabilities(value)], [HARDWARE_GPU_SLOTS, (value: JsonValue | null) => host.handleSavedGpuSettings(value)]);
    }

    if (host.hasGrantedAction('HARDWARE_READ')) {
        subscriptions.push([HARDWARE_GPU_SOAIBENCH_RUNS, (value: JsonValue | null) => host.handleSoAIBenchRunsUpdate(value)]);
    }

    if (host.hasProcessPanel() && host.hasGrantedAction('HW_PROCESS_VIEW')) {
        subscriptions.push([HARDWARE_PROCESSES, (value: JsonValue | null) => host.handleProcessResourceUpdate(value)]);
    }

    let resourceSubscriptions: ResourceStreamSubscription[] = [];
    try {
        resourceSubscriptions = subscribeResourceStateStreamBatch({
            label: 'Hardware realtime',
            bindings: subscriptions.map(([resource, handler]) => ({ resource, handler })),
            subscribeToData: (resource, handler) => host.subscribeToData(resource, handler)
        });
        for (const subscription of resourceSubscriptions) {
            const disposer = subscription.dispose;
            host.realtimeSubscriptionHandles.add(disposer);
            host.trackDisposable(disposer, () => {
                host.realtimeSubscriptionHandles.delete(disposer);
                disposer();
                if (!host.realtimeSubscriptionHandles.size) {
                    host.realtimeStreamActive = false;
                }
            });
        }
    } catch (error) {
        host.realtimeStreamActive = false;
        for (const subscription of resourceSubscriptions) {
            host.resources?.untrack?.(subscription.dispose);
            host.realtimeSubscriptionHandles.delete(subscription.dispose);
        }
        try {
            disposeResourceStreamSubscriptions(resourceSubscriptions);
        } catch (cleanupError) {
            throw new AggregateError([ensureError(error), ensureError(cleanupError)], 'Hardware realtime setup failed and cleanup also failed');
        }
        throw ensureError(error);
    }
};

const disposeRealtimeHandles = (host: HardwareRealtimeHost): void => {
    if (!host.realtimeSubscriptionHandles.size) {
        return;
    }
    const resources = host.resources;
    let firstError: Error | null = null;
    for (const disposer of host.realtimeSubscriptionHandles) {
        resources?.untrack?.(disposer);
        runCleanupCallbacks([disposer], (runtimeError) => {
            firstError = firstError ?? runtimeError;
        });
    }
    host.realtimeSubscriptionHandles.clear();
    host.realtimeStreamActive = false;
    if (firstError) {
        throw firstError;
    }
};

const initializeHardwareRealtime = (host: HardwareRealtimeHost, streams: HardwareRealtimeStreams, logger: (level: LogLevel, message: string, error?: Error) => void, signal?: AbortSignal): Promise<void> => {
    return (async (): Promise<void> => {
        try {
            const options = buildSignalRequestOptions({ signal });
            await host.resolveStreamManager(options);
            throwIfAborted(signal);
            setupRealtimeSubscriptions(host, streams);
            await host.ensureDataSubscriptions(options);
            logger('info', 'Hardware realtime subscriptions established');
        } catch (error) {
            try {
                disposeRealtimeHandles(host);
            } catch (cleanupError) {
                logger('warn', 'Hardware realtime cleanup failed', ensureError(cleanupError));
            }
            const runtimeError = ensureError(error);
            if (!signal?.aborted) {
                logger('warn', 'Hardware stream initialization failed', runtimeError);
            }
            throw runtimeError;
        }
    })();
};

export { disposeRealtimeHandles, initializeHardwareRealtime, setupRealtimeSubscriptions };
export type { HardwareRealtimeHost, HardwareRealtimeStreams };
