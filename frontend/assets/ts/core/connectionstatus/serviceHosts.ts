/* SoAI - Shared frontend connection status service hosts [frontend/assets/ts/core/connectionstatus/serviceHosts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createEnsureStreamHost, createSnapshotProcessingHost, createStopStreamHost } from '@core/connectionstatus/hostFactories.ts';
import type { EnsureStreamHost, SnapshotProcessingHost, StopStreamHost } from '@core/connectionstatus/internalContracts.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import type { ConnectionStatusState } from '@core/connectionstatus/state.ts';
import type { ModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface ConnectionStatusServiceHostContext {
    state: ConnectionStatusState;
    log: ModuleLogger;
    ensureDeclaredResources: () => Promise<StreamRuntimeOwners | null>;
    ensureStream: () => Promise<void> | null;
    processSnapshot: (snapshot: JsonValue, eventType: string) => void;
    setConnected: (value: boolean) => void;
    readQueueDepth: () => number | null;
    clearRestartTimer: () => void;
    scheduleStreamRestart: () => void;
    emitTelemetry: (stage: string, message: string, severity: 'debug' | 'info' | 'warn' | 'error', data?: JsonValue, queueDepth?: number | null) => void;
    publishMetric: (stage: string, extra?: JsonObject, queueDepth?: number | null) => void;
    emitEvent: (type: string, data?: { raw?: JsonValue; error?: JsonValue; attempt?: number | null; maxAttempts?: number | null }) => void;
    emitConnectionError: (error: Error, reason: string) => void;
    resetRestartInfoState: (context?: JsonObject) => void;
    rejectWaiters: (error: Error) => void;
}

interface ConnectionStatusServiceHosts {
    ensureStream: EnsureStreamHost;
    stopStream: StopStreamHost;
    snapshotProcessing: SnapshotProcessingHost;
}

const createConnectionStatusServiceHosts = (context: ConnectionStatusServiceHostContext): ConnectionStatusServiceHosts => {
    const emitTelemetry = ({ stage, message, severity, data, queueDepth }: { stage: string; message: string; severity: 'debug' | 'info' | 'warn' | 'error'; data?: JsonValue; queueDepth?: number | null }): void => {
        context.emitTelemetry(stage, message, severity, data, queueDepth);
    };
    const publishMetric = (stage: string, extra?: JsonObject, queueDepth?: number | null): void => {
        context.publishMetric(stage, extra || {}, queueDepth);
    };
    const emitEvent = (type: string, data?: { raw?: JsonValue; error?: JsonValue; attempt?: number | null; maxAttempts?: number | null }): void => {
        context.emitEvent(type, data || {});
    };
    return {
        ensureStream: createEnsureStreamHost({
            state: context.state,
            log: context.log,
            ensureDeclaredResources: context.ensureDeclaredResources,
            ensureStream: context.ensureStream,
            processSnapshot: context.processSnapshot,
            setConnected: context.setConnected,
            readQueueDepth: context.readQueueDepth,
            clearRestartTimer: context.clearRestartTimer,
            emitTelemetry,
            publishMetric,
            emitEvent,
            resetRestartInfoState: context.resetRestartInfoState,
            rejectWaiters: context.rejectWaiters
        }),
        stopStream: createStopStreamHost({
            state: context.state,
            log: context.log,
            setConnected: context.setConnected,
            readQueueDepth: context.readQueueDepth,
            clearRestartTimer: context.clearRestartTimer,
            emitTelemetry,
            publishMetric,
            emitEvent,
            resetRestartInfoState: context.resetRestartInfoState,
            rejectWaiters: context.rejectWaiters
        }),
        snapshotProcessing: createSnapshotProcessingHost({
            state: context.state,
            log: context.log,
            setConnected: context.setConnected,
            clearRestartTimer: context.clearRestartTimer,
            scheduleStreamRestart: context.scheduleStreamRestart,
            readQueueDepth: context.readQueueDepth,
            emitTelemetry,
            publishMetric,
            emitEvent,
            emitConnectionError: context.emitConnectionError,
            resetRestartInfoState: context.resetRestartInfoState
        })
    };
};

export { createConnectionStatusServiceHosts };
export type { ConnectionStatusServiceHostContext, ConnectionStatusServiceHosts };
