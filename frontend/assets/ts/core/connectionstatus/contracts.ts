/* SoAI - Shared frontend connection status boundary contracts [frontend/assets/ts/core/connectionstatus/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { type ConnectionStatusState } from '@core/connectionstatus/state.ts';

interface MaintenanceState {
    active: boolean;
    pausesTransport: boolean;
}

interface SubscribeConnectionOptions {
    emitCurrent?: boolean;
}

interface SubscribeRestartOptions {
    immediate?: boolean;
}

interface HoldOptions {
    timeoutMs?: number;
}

interface InitialSnapshotOptions {
    timeout?: number;
}

interface StreamPayloadContext {
    type?: JsonValue;
    raw?: JsonValue | null;
}

interface SnapshotProcessorDependencies {
    emitTelemetry: (stage: string, message: string, severity: 'debug' | 'info' | 'warn' | 'error', data: JsonValue, queueDepth?: number | null) => void;
    publishMetric: (stage: string, extra?: JsonObject, queueDepth?: number | null) => void;
    emitEvent: (type: string, data: { raw?: JsonValue; error?: JsonValue; attempt?: number | null; maxAttempts?: number | null }) => void;
    emitConnectionError: (error: Error, reason: string) => void;
    scheduleStreamRestart: () => void;
    setConnected: (value: boolean) => void;
    clearRestartTimer: () => void;
    readQueueDepth: () => number | null;
    resetRestartInfoState: () => void;
}

interface StreamStartContext {
    state: ConnectionStatusState;
    emitTelemetry: (stage: string, message: string, severity: 'debug' | 'info' | 'warn' | 'error', data: JsonValue, queueDepth?: number | null) => void;
    publishMetric: (stage: string, extra?: JsonObject, queueDepth?: number | null) => void;
    emitEvent: (type: string, data: { raw?: JsonValue; error?: JsonValue; attempt?: number | null; maxAttempts?: number | null }) => void;
    emitConnectionError: (error: Error, reason: string) => void;
    setConnected: (value: boolean) => void;
    clearRestartTimer: () => void;
    clearTimer: (timerId: number | null) => void;
    readQueueDepth: () => number | null;
    rejectWaiters: (error: Error) => void;
    onStreamSnapshot: (snapshot: JsonValue, context: StreamPayloadContext) => void;
    onResolveManager: () => Promise<JsonValue | null>;
}

export type { MaintenanceState, SubscribeConnectionOptions, SubscribeRestartOptions, HoldOptions, InitialSnapshotOptions, StreamPayloadContext, SnapshotProcessorDependencies, StreamStartContext };
