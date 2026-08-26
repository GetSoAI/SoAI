/* SoAI - Shared frontend connection status internal contracts [frontend/assets/ts/core/connectionstatus/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import type { ConnectionStatusState } from '@core/connectionstatus/state.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface ConnectionEventPayload {
    raw?: JsonValue;
    error?: JsonValue;
    attempt?: number | null;
    maxAttempts?: number | null;
}

interface StreamPayloadContext {
    type?: JsonValue;
    raw?: JsonValue | null;
}

interface TelemetryPayload {
    stage: string;
    message: string;
    severity: 'debug' | 'info' | 'warn' | 'error';
    data: JsonValue;
    queueDepth?: number | null;
}

interface EnsureStreamHost {
    state: ConnectionStatusState;
    log: ModuleLogger;
    ensureDeclaredResources: () => Promise<StreamRuntimeOwners | null>;
    ensureStream: () => Promise<void> | null;
    processSnapshot: (snapshot: JsonValue, eventType: string) => void;
    setConnected: (value: boolean) => void;
    readQueueDepth: () => number | null;
    clearRestartTimer: () => void;
    emitTelemetry: (payload: TelemetryPayload) => void;
    publishMetric: (stage: string, extra?: JsonObject, queueDepth?: number | null) => void;
    emitEvent: (type: string, data?: ConnectionEventPayload) => void;
    rejectWaiters: (error: Error) => void;
}

interface SnapshotProcessingHost {
    state: ConnectionStatusState;
    log: ModuleLogger;
    setConnected: (value: boolean) => void;
    clearRestartTimer: () => void;
    scheduleStreamRestart: () => void;
    readQueueDepth: () => number | null;
    emitTelemetry: (payload: TelemetryPayload) => void;
    publishMetric: (stage: string, extra?: JsonObject, queueDepth?: number | null) => void;
    emitEvent: (type: string, data?: ConnectionEventPayload) => void;
    emitConnectionError: (error: Error, reason: string) => void;
    resetRestartInfoState: (context?: JsonObject) => void;
}

interface StopStreamHost {
    state: ConnectionStatusState;
    clearRestartTimer: () => void;
    setConnected: (value: boolean) => void;
    readQueueDepth: () => number | null;
    emitTelemetry: (payload: TelemetryPayload) => void;
    publishMetric: (stage: string, extra?: JsonObject, queueDepth?: number | null) => void;
    emitEvent: (type: string, data?: ConnectionEventPayload) => void;
    resetRestartInfoState: (context?: JsonObject) => void;
    rejectWaiters: (error: Error) => void;
}

export type { ConnectionEventPayload, EnsureStreamHost, SnapshotProcessingHost, StopStreamHost, StreamPayloadContext, TelemetryPayload };
