/* SoAI - Logging feature adapters [frontend/assets/ts/features/logging/logstreamservice/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getStreamRuntime } from '@core/realtime/streammanager/public.ts';
import type { TelemetryFields, TelemetryValue } from '@core/telemetry/contracts.ts';
import { ensureStreamManagerReady } from '@core/realtime/streammanager/readiness.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isLogStreamManager } from '@features/logging/logstreamservice/guards.ts';
import type { LogApi, LogBundleSubscription, StreamManagerWithLogs } from '@features/logging/logstreamservice/types.ts';

interface ApiState {
    api: LogApi | null;
}

interface StreamManagerState {
    streamManager: StreamManagerWithLogs | null;
}

interface StreamManagerReadyDependencies {
    ensureDeclaredResources: () => Promise<void>;
}

interface SnapshotSubscriptionState {
    snapshotMeta: { source: string };
    snapshotSubscription: LogBundleSubscription | null;
}

interface SnapshotSubscriptionDependencies {
    applySnapshot: (value: JsonValue | null | undefined) => void;
    logWarn: (message: string, detail?: TelemetryValue) => void;
    publishMetric: (metric: string, value: number, tags: TelemetryFields) => void;
}

const ensureLogApiReady = async (state: ApiState): Promise<LogApi> => {
    const api = state.api;
    if (!api) {
        throw new Error('API client is unavailable for LogStreamService');
    }
    if (isFunction(api.whenReady)) {
        await api.whenReady({ allowDiscovery: true });
    }
    return api;
};

const resolveLogStreamManager = (state: StreamManagerState): StreamManagerWithLogs => {
    if (!state.streamManager) {
        const manager = getStreamRuntime();
        if (!isLogStreamManager(manager)) {
            throw new Error('Stream runtime must expose log resource, subscription, and connection owners before LogStreamService');
        }
        state.streamManager = manager;
    }
    return state.streamManager;
};

const ensureLogStreamManagerReady = async (state: StreamManagerState, dependencies: StreamManagerReadyDependencies): Promise<StreamManagerWithLogs> => {
    await dependencies.ensureDeclaredResources();
    const manager = resolveLogStreamManager(state);
    await ensureStreamManagerReady(manager.resources, { allowDiscovery: true });
    return manager;
};

const awaitLogSnapshotReady = async (subscription: LogBundleSubscription, source: string, dependencies: Pick<SnapshotSubscriptionDependencies, 'logWarn' | 'publishMetric'>): Promise<void> => {
    const ready = subscription.ready;
    if (!ready) {
        return;
    }
    try {
        if (isFunction(ready)) {
            await ready();
        } else {
            await ready;
        }
        dependencies.publishMetric('logs.snapshot.ready', 1, { source });
    } catch (error) {
        const runtimeError = ensureError(error);
        dependencies.logWarn('Snapshot readiness failed', runtimeError);
    }
};

const ensureLogSnapshotReady = async (state: SnapshotSubscriptionState, manager: StreamManagerWithLogs, dependencies: SnapshotSubscriptionDependencies): Promise<void> => {
    if (state.snapshotSubscription) {
        await awaitLogSnapshotReady(state.snapshotSubscription, state.snapshotMeta.source, dependencies);
        return;
    }
    const subscription = manager.subscriptions.subscribeBundle(
        'logs',
        {
            aliases: {
                entries: dependencies.applySnapshot
            },
            onError: (error: Error | string | null): void => {
                dependencies.logWarn('Log bundle error', error);
            }
        },
        { signal: null }
    );
    if (!subscription) {
        throw new Error('Stream manager log bundle unavailable');
    }
    state.snapshotSubscription = subscription;
    await awaitLogSnapshotReady(subscription, state.snapshotMeta.source, dependencies);
};

export { ensureLogApiReady, ensureLogSnapshotReady, ensureLogStreamManagerReady, resolveLogStreamManager };
