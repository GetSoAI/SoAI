/* SoAI - Logging feature log stream service public contracts [frontend/assets/ts/features/logging/logstreamservice/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SystemLogSnapshot } from '@core/api/contracts/systemContracts.ts';
import type { LogEntry } from '@core/logNormalization.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

type ConnectionStatus = 'connecting' | 'connected' | 'error' | 'reconnecting';
type ReplayMode = 'live' | 'history' | 'replay';

interface SnapshotMeta {
    source: string;
    limit: number;
    receivedAt: number;
}

interface SnapshotPayload extends SnapshotMeta {
    entries: LogEntry[];
}

interface LogEvent {
    type: 'log';
    entry: LogEntry;
    source?: string;
    mode?: ReplayMode;
}

interface HistoryEvent {
    type: 'history';
    entries: LogEntry[];
    source?: string;
    limit: number;
}

interface SnapshotEvent {
    type: 'snapshot';
    status: 'replay-complete' | 'refreshed';
    total: number;
    limit: number;
    source?: string;
}

interface ConnectionEvent {
    type: 'connection';
    status: ConnectionStatus;
    source?: string;
}

type LogStreamEvent = LogEvent | HistoryEvent | SnapshotEvent | ConnectionEvent;

type LogStreamListener = (event: LogStreamEvent) => void;

interface LogSubscriberOptions {
    replayLimit?: number;
    source?: string;
}

interface LogBundleHandlers {
    aliases?: {
        entries?: (snapshot: JsonValue | null | undefined) => void;
    };
    onError?: (error: Error | string | null) => void;
}

interface LogBundleSubscription {
    ready?: PromiseLike<void> | (() => PromiseLike<void> | void);
    abort?: () => void;
    unsubscribe?: () => void;
}

interface StreamSubscriptionHandle {
    unsubscribe?: () => void;
    close?: () => void;
    abort?: () => void;
    detach?: () => void;
}

interface StreamLogHandlers {
    onOpen?: () => void;
    onUpdate?: (payload: JsonValue | null | undefined, type?: string | null, raw?: JsonValue | null | undefined) => void;
    onError?: (error: Error) => void;
    onClose?: () => void;
}

interface StreamManagerWithLogs {
    resources: {
        ensureReady(options?: { allowDiscovery?: boolean }): Promise<void>;
    };
    subscriptions: {
        subscribeBundle(bundleName: string, handlers: LogBundleHandlers, options?: { signal?: AbortSignal | null }): LogBundleSubscription | null;
        unsubscribe(handle: StreamSubscriptionHandle): void;
    };
    connection: {
        streamLogs(source: string, handlers: StreamLogHandlers, options?: { historyLimit?: number }): StreamSubscriptionHandle | null;
    };
}

interface LogApiOptions {
    query: { limit: number };
    throwOnError?: boolean;
    notifyOnError?: boolean;
    logErrors?: boolean;
}

interface LogApi {
    whenReady?: (options?: { allowDiscovery?: boolean }) => Promise<string>;
    system?: {
        logs?: (source: string, options: LogApiOptions) => Promise<SystemLogSnapshot>;
    };
}

interface SnapshotExpansionTask {
    limit: number;
    promise: Promise<void>;
}

interface NormalizedStreamMessage {
    type: string | null;
    payload: JsonObject | null;
}

export { type ConnectionStatus, type ConnectionEvent, type HistoryEvent, type LogApi, type LogApiOptions, type LogBundleHandlers, type LogBundleSubscription, type LogEvent, type LogStreamEvent, type LogStreamListener, type LogSubscriberOptions, type NormalizedStreamMessage, type ReplayMode, type SnapshotExpansionTask, type SnapshotMeta, type SnapshotPayload, type SnapshotEvent, type StreamLogHandlers, type StreamManagerWithLogs, type StreamSubscriptionHandle };
