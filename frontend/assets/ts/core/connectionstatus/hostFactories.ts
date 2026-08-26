/* SoAI - Shared frontend connection status host factories [frontend/assets/ts/core/connectionstatus/hostFactories.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { EnsureStreamHost, SnapshotProcessingHost, StopStreamHost } from '@core/connectionstatus/internalContracts.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import type { ConnectionStatusState } from '@core/connectionstatus/state.ts';
import type { ModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface ConnectionStatusHostFactoryContext {
    state: ConnectionStatusState;
    log: ModuleLogger;
    ensureDeclaredResources?: () => Promise<StreamRuntimeOwners | null>;
    ensureStream?: () => Promise<void> | null;
    processSnapshot?: (snapshot: JsonValue, eventType: string) => void;
    setConnected: (value: boolean) => void;
    readQueueDepth: () => number | null;
    clearRestartTimer: () => void;
    scheduleStreamRestart?: () => void;
    emitTelemetry: EnsureStreamHost['emitTelemetry'];
    publishMetric: EnsureStreamHost['publishMetric'];
    emitEvent: EnsureStreamHost['emitEvent'];
    emitConnectionError?: (error: Error, reason: string) => void;
    resetRestartInfoState: (context?: JsonObject) => void;
    rejectWaiters?: (error: Error) => void;
}

const createEnsureStreamHost = (context: ConnectionStatusHostFactoryContext): EnsureStreamHost => {
    if (!context.ensureDeclaredResources || !context.ensureStream || !context.processSnapshot || !context.rejectWaiters) {
        throw new Error('EnsureStreamHost requires stream bootstrap callbacks');
    }
    return {
        state: context.state,
        log: context.log,
        ensureDeclaredResources: context.ensureDeclaredResources,
        ensureStream: context.ensureStream,
        processSnapshot: context.processSnapshot,
        setConnected: context.setConnected,
        readQueueDepth: context.readQueueDepth,
        clearRestartTimer: context.clearRestartTimer,
        emitTelemetry: context.emitTelemetry,
        publishMetric: context.publishMetric,
        emitEvent: context.emitEvent,
        rejectWaiters: context.rejectWaiters
    };
};

const createStopStreamHost = (context: ConnectionStatusHostFactoryContext): StopStreamHost => {
    if (!context.rejectWaiters) {
        throw new Error('StopStreamHost requires waiter rejection');
    }
    return {
        state: context.state,
        clearRestartTimer: context.clearRestartTimer,
        setConnected: context.setConnected,
        readQueueDepth: context.readQueueDepth,
        emitTelemetry: context.emitTelemetry,
        publishMetric: context.publishMetric,
        emitEvent: context.emitEvent,
        resetRestartInfoState: context.resetRestartInfoState,
        rejectWaiters: context.rejectWaiters
    };
};

const createSnapshotProcessingHost = (context: ConnectionStatusHostFactoryContext): SnapshotProcessingHost => {
    if (!context.scheduleStreamRestart || !context.emitConnectionError) {
        throw new Error('SnapshotProcessingHost requires restart callbacks');
    }
    return {
        state: context.state,
        log: context.log,
        setConnected: context.setConnected,
        clearRestartTimer: context.clearRestartTimer,
        scheduleStreamRestart: context.scheduleStreamRestart,
        readQueueDepth: context.readQueueDepth,
        emitTelemetry: context.emitTelemetry,
        publishMetric: context.publishMetric,
        emitEvent: context.emitEvent,
        emitConnectionError: context.emitConnectionError,
        resetRestartInfoState: context.resetRestartInfoState
    };
};

export { createEnsureStreamHost, createSnapshotProcessingHost, createStopStreamHost };
