/* SoAI - Logging feature log stream service effects [frontend/assets/ts/features/logging/logstreamservice/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import type { TelemetryFields } from '@core/telemetry/contracts.ts';
import type { TabStatePayload } from '@core/state/TabStateCoordinator.ts';
import { LOG_BUNDLE_STATE_KEY, LOG_RESOURCE_NAME, MAX_BUFFER_SIZE, SHARED_BUFFER_SYNC_DELAY_MS } from '@features/logging/logstreamservice/constants.ts';
import { replayBufferToSubscriber, updateBufferFromResolved, validateReplayLimit, type LogStreamLogger, type LogStreamSubscriberState } from '@features/logging/logstreamservice/actions.ts';
import { resolveSnapshotPayload } from '@features/logging/logstreamservice/mappers.ts';
import type { SnapshotPayload } from '@features/logging/logstreamservice/types.ts';
import type { LogEntry } from '@core/logNormalization.ts';
import type { LogDataValidator } from '@core/logvalidation/public.ts';
import type { StateManager } from '@core/state/public.ts';

interface SharedSyncState {
    currentBufferSize: number;
    sharedSnapshotEntries: LogEntry[];
    snapshotMeta: { source: string; limit: number; receivedAt: number };
    sharedSyncScheduled: boolean;
    sharedSyncTimerId: number | null;
}

interface SnapshotResolutionDependencies {
    normalizeLogEntry: (entry: JsonValue | null | undefined) => LogEntry;
    logger: Pick<LogStreamLogger, 'logWarn'>;
}

const cancelPendingSharedSync = (state: SharedSyncState, clearTimer: (id: number) => void): void => {
    if (state.sharedSyncTimerId !== null) {
        clearTimer(state.sharedSyncTimerId);
        state.sharedSyncTimerId = null;
    }
    state.sharedSyncScheduled = false;
};

const flushSharedBufferToState = (state: SharedSyncState, stateService: StateManager, clearTimer: (id: number) => void): void => {
    cancelPendingSharedSync(state, clearTimer);
    const timestamp = Date.now();
    const limit = Math.min(state.currentBufferSize, MAX_BUFFER_SIZE);
    const entries = state.sharedSnapshotEntries.length > limit ? state.sharedSnapshotEntries.slice(-limit) : state.sharedSnapshotEntries.slice();

    state.snapshotMeta = { source: state.snapshotMeta.source, limit, receivedAt: timestamp };
    const snapshot = {
        name: LOG_RESOURCE_NAME,
        value: { entries, source: state.snapshotMeta.source, limit, receivedAt: timestamp },
        status: 'ready',
        updatedAt: timestamp
    };

    const updateState = (key: string): void => {
        const existing = stateService.getTabState(key, null);
        const next = isObject(existing) ? existing : {};
        stateService.setTabState(key, {
            ...next,
            [LOG_RESOURCE_NAME]: snapshot
        });
    };
    updateState(LOG_BUNDLE_STATE_KEY);
    updateState('stream.bundle.detached');
};

const scheduleSharedBufferSync = (state: SharedSyncState, force: boolean, setTimer: (callback: () => void, delayMs: number) => number | null, clearTimer: (id: number) => void, flushSharedBuffer: () => void): void => {
    if (force) {
        cancelPendingSharedSync(state, clearTimer);
        flushSharedBuffer();
        return;
    }
    if (state.sharedSyncScheduled) {
        return;
    }
    state.sharedSyncScheduled = true;
    const timerId = setTimer(() => {
        state.sharedSyncScheduled = false;
        state.sharedSyncTimerId = null;
        flushSharedBuffer();
    }, SHARED_BUFFER_SYNC_DELAY_MS);
    if (timerId === null) {
        state.sharedSyncScheduled = false;
        return;
    }
    state.sharedSyncTimerId = timerId;
};

const restoreBufferFromState = (state: LogStreamSubscriberState, stateService: StateManager, resolveSnapshot: (payload: JsonValue | null | undefined) => SnapshotPayload | null): void => {
    const readState = (key: string): JsonValue | null | undefined => {
        const container = stateService.getTabState(key, null);
        if (!container || !isObject(container)) {
            return null;
        }
        const resource = container[LOG_RESOURCE_NAME];
        if (!resource || !isObject(resource)) {
            return null;
        }
        return resource['value'];
    };

    const resolved = resolveSnapshot(readState(LOG_BUNDLE_STATE_KEY) || readState('stream.bundle.detached'));
    if (resolved && resolved.source === state.snapshotMeta.source) {
        updateBufferFromResolved(state, resolved);
    }
};

const readSnapshotMetaSignature = (snapshotValue: JsonValue | null | undefined): { source: string; limit: number; receivedAt: number } | null => {
    if (!snapshotValue || !isObject(snapshotValue)) {
        return null;
    }
    const receivedAtRaw = snapshotValue['receivedAt'];
    const receivedAt = typeof receivedAtRaw === 'number' && Number.isFinite(receivedAtRaw) ? receivedAtRaw : null;
    if (!receivedAt || receivedAt <= 0) {
        return null;
    }
    const limitRaw = snapshotValue['limit'];
    const limit = typeof limitRaw === 'number' && Number.isFinite(limitRaw) ? Math.floor(limitRaw) : null;
    if (!limit || limit <= 0) {
        return null;
    }
    const sourceRaw = snapshotValue['source'];
    const source = isString(sourceRaw) ? sourceRaw.trim() : '';
    if (!source) {
        return null;
    }
    return { source, limit, receivedAt };
};

const handleTabStateChange = (state: LogStreamSubscriberState, payload: TabStatePayload, validator: LogDataValidator, logger: Pick<LogStreamLogger, 'logError'>, resolveSnapshot: (value: JsonValue | null | undefined) => SnapshotPayload | null): boolean => {
    if (payload.key !== LOG_BUNDLE_STATE_KEY && payload.key !== 'stream.bundle.detached') {
        return false;
    }
    const container = payload.value;
    if (!container || !isObject(container)) {
        return false;
    }
    const snapshot = container[LOG_RESOURCE_NAME];
    if (!snapshot || !isObject(snapshot)) {
        return false;
    }
    const value = snapshot['value'];

    const signature = readSnapshotMetaSignature(value);
    if (signature && signature.source !== state.snapshotMeta.source) {
        return false;
    }
    if (signature && state.logBuffer.length > 0) {
        if (signature.source === state.snapshotMeta.source && signature.limit === state.snapshotMeta.limit && signature.receivedAt === state.snapshotMeta.receivedAt) {
            return false;
        }
        if (signature.receivedAt < state.snapshotMeta.receivedAt) {
            return false;
        }
    }

    const resolved = resolveSnapshot(value);
    if (!resolved) {
        return false;
    }
    if (resolved.source !== state.snapshotMeta.source) {
        return false;
    }
    updateBufferFromResolved(state, resolved);
    state.subscribers.forEach((limit, callback) => {
        if (state.replayedSubscribers.has(callback)) {
            return;
        }
        const replayLimit = validateReplayLimit(validator, limit, logger);
        const effectiveLimit = Math.min(state.logBuffer.length, replayLimit);
        if (effectiveLimit <= 0) {
            return;
        }
        replayBufferToSubscriber(state, callback, replayLimit);
        state.replayedSubscribers.add(callback);
    });
    return true;
};

const buildSnapshotResolver = (state: Pick<LogStreamSubscriberState, 'snapshotMeta'>, dependencies: SnapshotResolutionDependencies): ((payload: JsonValue | null | undefined) => SnapshotPayload | null) => {
    return (payload: JsonValue | null | undefined): SnapshotPayload | null =>
        resolveSnapshotPayload({
            payload,
            snapshotMeta: state.snapshotMeta,
            normalizeLogEntry: dependencies.normalizeLogEntry,
            logWarn: dependencies.logger.logWarn
        });
};

const applyResolvedSnapshot = (state: LogStreamSubscriberState, resolved: SnapshotPayload, syncSharedBuffer: () => void, publishMetric: (metric: string, value: number, tags: TelemetryFields) => void): void => {
    updateBufferFromResolved(state, resolved);
    state.replayedSubscribers.clear();
    syncSharedBuffer();
    publishMetric('logs.snapshot.entries', state.logBuffer.length, {
        source: state.snapshotMeta.source,
        limit: state.snapshotMeta.limit
    });
};

export { applyResolvedSnapshot, buildSnapshotResolver, cancelPendingSharedSync, flushSharedBufferToState, handleTabStateChange, restoreBufferFromState, scheduleSharedBufferSync };
export type { SharedSyncState };
