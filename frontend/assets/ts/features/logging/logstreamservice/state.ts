/* SoAI - Logging feature log stream service state [frontend/assets/ts/features/logging/logstreamservice/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LogEntry } from '@core/logNormalization.ts';
import { DEFAULT_LOG_SOURCE, DEFAULT_REPLAY_LIMIT, MAX_BUFFER_SIZE } from '@features/logging/logstreamservice/constants.ts';
import type { LogApi, LogBundleSubscription, LogStreamListener, SnapshotExpansionTask, SnapshotMeta, StreamManagerWithLogs, StreamSubscriptionHandle } from '@features/logging/logstreamservice/types.ts';

interface LogStreamMutableState {
    subscribers: Map<LogStreamListener, number>;
    replayedSubscribers: Set<LogStreamListener>;
    logBuffer: LogEntry[];
    snapshotMeta: SnapshotMeta;
    connectionGeneration: number;
    connectionStartedAt: number;
    isConnected: boolean;
    connectionHandle: StreamSubscriptionHandle | null;
    connectPromise: Promise<StreamSubscriptionHandle | null> | null;
    streamManager: StreamManagerWithLogs | null;
    api: LogApi | null;
    currentBufferSize: number;
    snapshotSubscription: LogBundleSubscription | null;
    sharedSnapshotEntries: LogEntry[];
    pendingSnapshotExpansion: SnapshotExpansionTask | null;
    sharedSyncScheduled: boolean;
    sharedSyncTimerId: number | null;
    reconnectNoticeTimerId: number | null;
    maintenanceSubscription: (() => void) | null;
    recoverySuspended: boolean;
    teardownInProgress: boolean;
}

const createInitialSnapshotMeta = (source: string): SnapshotMeta => {
    return { source, limit: DEFAULT_REPLAY_LIMIT, receivedAt: Date.now() };
};

const createLogStreamMutableState = (source: string = DEFAULT_LOG_SOURCE): LogStreamMutableState => {
    return {
        subscribers: new Map(),
        replayedSubscribers: new Set(),
        logBuffer: [],
        snapshotMeta: createInitialSnapshotMeta(source),
        connectionGeneration: 0,
        connectionStartedAt: 0,
        isConnected: false,
        connectionHandle: null,
        connectPromise: null,
        streamManager: null,
        api: null,
        currentBufferSize: DEFAULT_REPLAY_LIMIT,
        snapshotSubscription: null,
        sharedSnapshotEntries: [],
        pendingSnapshotExpansion: null,
        sharedSyncScheduled: false,
        sharedSyncTimerId: null,
        reconnectNoticeTimerId: null,
        maintenanceSubscription: null,
        recoverySuspended: false,
        teardownInProgress: false
    };
};

const resetMutableStateAfterDestroy = (state: LogStreamMutableState): void => {
    const source = state.snapshotMeta.source;
    state.subscribers.clear();
    state.replayedSubscribers.clear();
    state.logBuffer = [];
    state.sharedSnapshotEntries = [];
    state.currentBufferSize = DEFAULT_REPLAY_LIMIT;
    state.connectionGeneration += 1;
    state.connectionStartedAt = 0;
    state.connectPromise = null;
    state.connectionHandle = null;
    state.streamManager = null;
    state.api = null;
    state.snapshotSubscription = null;
    state.pendingSnapshotExpansion = null;
    state.sharedSyncScheduled = false;
    state.sharedSyncTimerId = null;
    state.reconnectNoticeTimerId = null;
    state.maintenanceSubscription = null;
    state.recoverySuspended = false;
    state.isConnected = false;
    state.teardownInProgress = false;
    state.snapshotMeta = createInitialSnapshotMeta(source);
};

const setSnapshotEntries = (state: LogStreamMutableState, entries: LogEntry[]): void => {
    state.logBuffer = entries.slice(-MAX_BUFFER_SIZE);
    state.sharedSnapshotEntries = state.logBuffer.map((entry) => Object.freeze({ ...entry }));
};

export { createLogStreamMutableState, resetMutableStateAfterDestroy, setSnapshotEntries };
export type { LogStreamMutableState };
