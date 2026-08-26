/* SoAI - Logging feature stream update handlers [frontend/assets/ts/features/logging/logstreamservice/streamUpdateHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { TelemetryFields } from '@core/telemetry/contracts.ts';
import type { LogEntry, LogNormalizer } from '@core/logNormalization.ts';
import type { LogDataValidator } from '@core/logvalidation/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { getTypeOf, isArray, isObject } from '@core/typeGuards.ts';
import { addEntryToBuffer, notifySubscribers, notifySubscribersBatch, toLogEvent, updateBufferFromResolved, type LogStreamLogger, type LogStreamSubscriberState } from '@features/logging/logstreamservice/actions.ts';
import { cleanStr } from '@features/logging/logstreamservice/constants.ts';
import { isHistoryReplayMode } from '@features/logging/logstreamservice/mappers.ts';
import type { LogStreamEvent } from '@features/logging/logstreamservice/types.ts';

interface StreamUpdateContext {
    state: LogStreamSubscriberState;
    normalizer: LogNormalizer;
    validator: LogDataValidator;
    logger: LogStreamLogger;
    publishMetric: (metric: string, value: number, tags: TelemetryFields) => void;
    syncSharedBuffer: () => void;
}

const handleLogBatch = (context: StreamUpdateContext, entries: JsonValue | null | undefined[], source: JsonValue | null | undefined, mode: JsonValue | null | undefined): void => {
    if (!isArray(entries)) {
        context.logger.logError(`Batch entries must be array, got ${getTypeOf(entries)}`);
        return;
    }
    const resolvedSource = cleanStr(source) || context.state.snapshotMeta.source;
    if (resolvedSource !== context.state.snapshotMeta.source) {
        context.logger.logWarn('Received log batch for inactive source', {
            active: context.state.snapshotMeta.source,
            received: resolvedSource
        });
        return;
    }
    const normalizedMode = cleanStr(mode)?.toLowerCase() ?? null;
    const eventMode: 'live' | 'history' | 'replay' = isHistoryReplayMode(normalizedMode) ? normalizedMode : 'live';

    context.publishMetric('logs.stream.batchSize', entries.length, {
        source: resolvedSource,
        mode: eventMode
    });

    const normalizedEntries: LogEntry[] = [];
    entries.forEach((entry) => {
        try {
            const normalized = context.normalizer.normalizeLogEntry(entry);
            normalizedEntries.push(normalized);
        } catch (error) {
            const runtimeError = ensureError(error);
            context.logger.logWarn('Batch entry invalid, skipping', runtimeError);
            context.publishMetric('logs.stream.invalidEntry', 1, { source: resolvedSource });
        }
    });

    if (eventMode === 'history') {
        updateBufferFromResolved(context.state, {
            entries: normalizedEntries,
            source: resolvedSource,
            limit: context.state.currentBufferSize,
            receivedAt: Date.now()
        });
        context.syncSharedBuffer();
        notifySubscribers(
            context.state,
            {
                type: 'history',
                entries: normalizedEntries,
                source: resolvedSource,
                limit: context.state.currentBufferSize
            },
            context.logger,
            context.publishMetric
        );
        return;
    }

    const batchEvents: LogStreamEvent[] = [];
    normalizedEntries.forEach((normalized) => {
        addEntryToBuffer(context.state, normalized, context.validator, { logError: context.logger.logError }, context.syncSharedBuffer);
        batchEvents.push(toLogEvent(normalized, resolvedSource, eventMode));
    });
    if (batchEvents.length > 0) {
        notifySubscribersBatch(context.state, batchEvents, context.logger, context.publishMetric);
    }
};

const handleSingleLogLine = (context: StreamUpdateContext, payload: JsonValue | null | undefined): void => {
    if (!payload || !isObject(payload)) {
        context.logger.logError('log_line payload missing entry field');
        return;
    }
    const entryValue = payload['entry'] !== undefined ? payload['entry'] : payload;
    const source = cleanStr(payload['source']) || context.state.snapshotMeta.source;
    const mode = cleanStr(payload['mode']);
    if (source !== context.state.snapshotMeta.source) {
        context.logger.logWarn('Received log line for inactive source', {
            active: context.state.snapshotMeta.source,
            received: source
        });
        return;
    }

    try {
        const entry = context.normalizer.normalizeLogEntry(entryValue);
        addEntryToBuffer(context.state, entry, context.validator, { logError: context.logger.logError }, context.syncSharedBuffer);
        context.publishMetric('logs.stream.singleEntry', 1, {
            source,
            mode: mode ? mode.toLowerCase() : 'live'
        });
        notifySubscribers(context.state, toLogEvent(entry, source, mode?.toLowerCase() ?? null), context.logger, context.publishMetric);
    } catch (error) {
        const runtimeError = ensureError(error);
        context.logger.logWarn('Single log entry invalid, skipping', runtimeError);
        context.publishMetric('logs.stream.invalidEntry', 1, { source });
    }
};

export { handleLogBatch, handleSingleLogLine };
export type { StreamUpdateContext };
