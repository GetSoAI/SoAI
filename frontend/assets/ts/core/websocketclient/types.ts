/* SoAI - Shared frontend WebSocket client public contracts [frontend/assets/ts/core/websocketclient/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface ConnectionStateInterface {
    initialize(): Promise<void>;
    getBaseUrl(): string | null;
    onChange(listener: (baseUrl: string | null) => void, options?: { immediate?: boolean }): () => void;
}

interface TimerState {
    heartbeat: ReturnType<typeof setTimeout> | null;
    connectionTimeout: ReturnType<typeof setTimeout> | null;
    reconnectStability: ReturnType<typeof setTimeout> | null;
}

interface WebSocketMessageData {
    type: string;
    protocolVersion: number;
    snapshotId: string | null;
    resource: string | null;
    data: JsonValue | undefined;
    error: JsonValue | undefined;
    message: JsonValue | undefined;
    timestampMs: number | null;
    raw: JsonObject;
}

interface SnapshotResponseEnvelope {
    resource: string;
    data: JsonValue;
    timestampMs: number | null;
}

interface PendingSnapshot {
    resolve: (value: SnapshotResponseEnvelope) => void;
    reject: (reason: Error) => void;
    timeout: ReturnType<typeof setTimeout>;
    removeAbortListener: (() => void) | null;
    resource: string;
    settled: boolean;
}

interface SnapshotRequestOptions {
    signal?: AbortSignal | undefined;
    timeoutMs?: number | undefined;
    retryOnReconnect?: boolean | undefined;
}

interface WaitForConnectionOptions {
    signal?: AbortSignal | undefined;
}

interface WebSocketDispatchContext {
    readonly connectionEpoch: number;
    readonly receiveSequence: number;
}

type EventCallback = (data: JsonValue, context: WebSocketDispatchContext) => void | Promise<void>;
type GlobalEventCallback = (eventType: string, data: JsonValue, context: WebSocketDispatchContext) => void | Promise<void>;

export type { ConnectionStateInterface, EventCallback, GlobalEventCallback, PendingSnapshot, SnapshotRequestOptions, SnapshotResponseEnvelope, TimerState, WaitForConnectionOptions, WebSocketDispatchContext, WebSocketMessageData };
