/* SoAI - Logging feature connection [frontend/assets/ts/features/logging/logstreamservice/connection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { TelemetryFields } from '@core/telemetry/contracts.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError, throwIfAborted, raceWithAbortSignal } from '@core/errors/abort.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { notifySubscribers, type LogStreamLogger } from '@features/logging/logstreamservice/actions.ts';
import { ensureLogApiReady, ensureLogSnapshotReady, ensureLogStreamManagerReady } from '@features/logging/logstreamservice/adapters.ts';
import { getNow } from '@features/logging/logstreamservice/constants.ts';
import { closeStreamSubscriptionHandle, handleStreamClosed, handleStreamError, handleStreamOpen, handleStreamUpdate, type StreamConnectionContext, type StreamUpdateContext } from '@features/logging/logstreamservice/events.ts';
import type { LogStreamMutableState } from '@features/logging/logstreamservice/state.ts';
import type { StreamSubscriptionHandle } from '@features/logging/logstreamservice/types.ts';

interface LogStreamConnectionRuntime {
    state: LogStreamMutableState;
    logger: LogStreamLogger;
    publishMetric: (metric: string, value: number, tags: TelemetryFields) => void;
    ensureDeclaredResources: () => Promise<void>;
    applySnapshot: (value: JsonValue | null | undefined) => void;
    createStreamUpdateContext: () => StreamUpdateContext;
    createStreamConnectionContext: (connectionGeneration?: number) => StreamConnectionContext;
}

const openLogStreamConnection = async (runtime: LogStreamConnectionRuntime, connectionGeneration: number, signal: AbortSignal): Promise<StreamSubscriptionHandle | null> => {
    throwIfAborted(signal);
    runtime.state.connectionStartedAt = getNow();
    await ensureLogApiReady(runtime.state, signal);
    const manager = await ensureLogStreamManagerReady(runtime.state, {
        ensureDeclaredResources: runtime.ensureDeclaredResources,
        signal
    });
    await raceWithAbortSignal(
        ensureLogSnapshotReady(runtime.state, manager, {
            applySnapshot: (value: JsonValue | null | undefined): void => {
                if (runtime.state.recoverySuspended || runtime.state.subscribers.size === 0) {
                    return;
                }
                runtime.applySnapshot(value);
            },
            logWarn: runtime.logger.logWarn,
            publishMetric: runtime.publishMetric
        }),
        signal
    );
    if (runtime.state.recoverySuspended || runtime.state.connectionGeneration !== connectionGeneration || runtime.state.subscribers.size === 0) {
        return null;
    }
    const connectionContext = runtime.createStreamConnectionContext(connectionGeneration);
    const handle = manager.connection.streamLogs(
        runtime.state.snapshotMeta.source,
        {
            onOpen: () => handleStreamOpen(connectionContext),
            onUpdate: (payload: JsonValue | null | undefined, eventType: JsonValue | null | undefined, raw: JsonValue | null | undefined): void => {
                if (runtime.state.recoverySuspended || runtime.state.connectionGeneration !== connectionGeneration || runtime.state.subscribers.size === 0) {
                    return;
                }
                handleStreamUpdate(runtime.createStreamUpdateContext(), payload, eventType, raw);
            },
            onError: (error: Error) => handleStreamError(connectionContext, error),
            onClose: () => handleStreamClosed(connectionContext)
        },
        {
            historyLimit: runtime.state.currentBufferSize
        }
    );
    if (runtime.state.recoverySuspended || runtime.state.connectionGeneration !== connectionGeneration || runtime.state.subscribers.size === 0) {
        closeStreamSubscriptionHandle(handle ?? null, manager, true);
        return null;
    }
    runtime.state.connectionHandle = handle ?? null;
    return runtime.state.connectionHandle;
};

const ensureLogStreamConnection = async (runtime: LogStreamConnectionRuntime): Promise<StreamSubscriptionHandle | null> => {
    if (runtime.state.connectPromise) {
        return runtime.state.connectPromise;
    }
    if (runtime.state.connectionHandle) {
        return runtime.state.connectionHandle;
    }
    if (runtime.state.subscribers.size === 0) {
        return null;
    }
    if (runtime.state.recoverySuspended || runtime.state.recoveryStopped) {
        return null;
    }
    runtime.state.recovery.cancel();
    runtime.state.connectionGeneration += 1;
    const connectionGeneration = runtime.state.connectionGeneration;
    const controller = new AbortController();
    runtime.state.connectionAbort = controller;
    const connectPromise = Promise.resolve().then(() => openLogStreamConnection(runtime, connectionGeneration, controller.signal));
    runtime.state.connectPromise = connectPromise;
    notifySubscribers(runtime.state, { type: 'connection', status: 'connecting' }, runtime.logger, runtime.publishMetric);
    try {
        return await connectPromise;
    } catch (error) {
        const runtimeError = ensureError(error);
        if (runtime.state.connectionGeneration !== connectionGeneration || runtime.state.subscribers.size === 0) {
            return null;
        }
        if (isAbortError(runtimeError) || isLifecycleCancellationError(runtimeError)) {
            handleStreamClosed(runtime.createStreamConnectionContext(connectionGeneration));
            return null;
        }
        if (!runtime.state.recoverySuspended) {
            handleStreamError(runtime.createStreamConnectionContext(connectionGeneration), runtimeError);
        }
    } finally {
        if (runtime.state.connectPromise === connectPromise) {
            runtime.state.connectPromise = null;
        }
    }
    return runtime.state.connectionHandle;
};

export { ensureLogStreamConnection };
export type { LogStreamConnectionRuntime };
