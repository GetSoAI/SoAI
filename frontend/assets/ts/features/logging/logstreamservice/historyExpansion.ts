/* SoAI - Logging feature history expansion [frontend/assets/ts/features/logging/logstreamservice/historyExpansion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { handleApiResult } from '@core/api/apiResultHandler.ts';
import type { TelemetryFields } from '@core/telemetry/contracts.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { LogEntry, LogNormalizer } from '@core/logNormalization.ts';
import type { LogDataValidator } from '@core/logvalidation/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction } from '@core/typeGuards.ts';
import { notifySubscribers, updateBufferFromResolved, validateReplayLimit, type LogStreamLogger } from '@features/logging/logstreamservice/actions.ts';
import { ensureLogApiReady } from '@features/logging/logstreamservice/adapters.ts';
import { DEFAULT_LOG_SOURCE, MAX_BUFFER_SIZE } from '@features/logging/logstreamservice/constants.ts';
import { restartRealtimeHistoryWindow } from '@features/logging/logstreamservice/realtimeHistoryRefresh.ts';
import type { LogStreamMutableState } from '@features/logging/logstreamservice/state.ts';
import type { LogApiOptions, StreamSubscriptionHandle } from '@features/logging/logstreamservice/types.ts';

interface HistoryExpansionRuntime {
    state: LogStreamMutableState;
    validator: LogDataValidator;
    normalizer: LogNormalizer;
    logger: LogStreamLogger;
    syncSharedBuffer: () => void;
    publishMetric: (metric: string, value: number, tags: TelemetryFields) => void;
    ensureConnection: () => Promise<StreamSubscriptionHandle | null>;
}

const loadExpandedSnapshot = async (runtime: HistoryExpansionRuntime, limit: number): Promise<void> => {
    const expectedGeneration = runtime.state.connectionGeneration;
    const expectedSource = runtime.state.snapshotMeta.source;
    const api = await ensureLogApiReady(runtime.state);
    const logsFunctionValue = api.system?.logs;
    if (!isFunction(logsFunctionValue)) {
        runtime.logger.logWarn('Log history API is unavailable');
        return;
    }
    const logHistoryOptions: LogApiOptions = { query: { limit } };
    const responsePayload = await handleApiResult(logsFunctionValue(expectedSource, logHistoryOptions), {
        boundaryName: 'LogStreamService',
        rethrow: false,
        notifyOnError: false,
        logErrors: false
    });
    if (responsePayload === null) {
        runtime.logger.logWarn('Log history API returned an invalid response');
        return;
    }
    if (expectedGeneration !== runtime.state.connectionGeneration || expectedSource !== runtime.state.snapshotMeta.source) {
        return;
    }
    const source = responsePayload.source;
    if (source !== expectedSource) {
        runtime.logger.logWarn('Log history API returned entries for a different source', {
            expected: expectedSource,
            received: source
        });
        return;
    }
    const normalizedEntries: LogEntry[] = [];
    const rawEntries: ReadonlyArray<JsonValue | null | undefined> = responsePayload.entries;
    rawEntries.forEach((entry, index) => {
        try {
            normalizedEntries.push(runtime.normalizer.normalizeLogEntry(entry));
        } catch (error) {
            const runtimeError = ensureError(error);
            runtime.logger.logWarn(`Snapshot history entry ${String(index)} invalid`, runtimeError);
        }
    });
    const bounded = Math.min(limit, MAX_BUFFER_SIZE);
    if (expectedGeneration !== runtime.state.connectionGeneration || expectedSource !== runtime.state.snapshotMeta.source) {
        return;
    }
    updateBufferFromResolved(runtime.state, {
        entries: normalizedEntries.slice(-bounded),
        source,
        limit: bounded,
        receivedAt: Date.now()
    });
    runtime.state.replayedSubscribers.clear();
    runtime.syncSharedBuffer();
    notifySubscribers(
        runtime.state,
        {
            type: 'snapshot',
            status: 'refreshed',
            total: runtime.state.logBuffer.length,
            limit: runtime.state.snapshotMeta.limit
        },
        runtime.logger,
        runtime.publishMetric
    );
};

const ensureHistoricalCoverage = async (runtime: HistoryExpansionRuntime, targetLimit: number): Promise<void> => {
    const bound = Math.min(validateReplayLimit(runtime.validator, targetLimit, runtime.logger), MAX_BUFFER_SIZE);
    if (runtime.state.snapshotMeta.source !== DEFAULT_LOG_SOURCE) {
        if (runtime.state.pendingSnapshotExpansion && runtime.state.pendingSnapshotExpansion.limit >= bound) {
            await runtime.state.pendingSnapshotExpansion.promise;
            return;
        }
        const task = restartRealtimeHistoryWindow({
            state: runtime.state,
            ensureConnection: runtime.ensureConnection
        });
        runtime.state.pendingSnapshotExpansion = { limit: bound, promise: task };
        try {
            await task;
        } finally {
            if (runtime.state.pendingSnapshotExpansion?.promise === task) {
                runtime.state.pendingSnapshotExpansion = null;
            }
        }
        return;
    }
    if (runtime.state.pendingSnapshotExpansion && runtime.state.pendingSnapshotExpansion.limit >= bound) {
        await runtime.state.pendingSnapshotExpansion.promise;
        return;
    }
    const task = loadExpandedSnapshot(runtime, bound);
    runtime.state.pendingSnapshotExpansion = { limit: bound, promise: task };
    try {
        await task;
    } finally {
        if (runtime.state.pendingSnapshotExpansion?.promise === task) {
            runtime.state.pendingSnapshotExpansion = null;
        }
    }
};

export { ensureHistoricalCoverage };
export type { HistoryExpansionRuntime };
