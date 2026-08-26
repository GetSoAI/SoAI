/* SoAI - Logging feature mappers [frontend/assets/ts/features/logging/logstreamservice/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { LogEntry } from '@core/logNormalization.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';
import { hasOwn, isArray, isObject, isString } from '@core/typeGuards.ts';
import { MAX_BUFFER_SIZE, cleanStr } from '@features/logging/logstreamservice/constants.ts';
import type { NormalizedStreamMessage, SnapshotMeta, SnapshotPayload } from '@features/logging/logstreamservice/types.ts';

interface SnapshotPayloadResolverOptions {
    payload: JsonValue | null | undefined;
    snapshotMeta: SnapshotMeta;
    normalizeLogEntry: (entry: JsonValue | null | undefined) => LogEntry;
    logWarn: (message: string, detail?: TelemetryValue) => void;
}

const resolveSnapshotPayload = (options: SnapshotPayloadResolverOptions): SnapshotPayload | null => {
    if (!options.payload || !isObject(options.payload)) {
        return null;
    }
    const payloadObject = options.payload;
    if (!isArray(payloadObject['entries'])) {
        options.logWarn('Snapshot payload missing entries array', options.payload);
        return null;
    }

    const entries: LogEntry[] = [];
    payloadObject['entries'].forEach((item, index) => {
        try {
            entries.push(options.normalizeLogEntry(item));
        } catch (error) {
            const runtimeError = ensureError(error);
            options.logWarn(`Snapshot entry ${String(index)} invalid`, runtimeError);
        }
    });

    const source = cleanStr(payloadObject['source']) || options.snapshotMeta.source;
    const limitValue = payloadObject['limit'];
    const rawLimit = typeof limitValue === 'number' && Number.isFinite(limitValue) ? Math.floor(limitValue) : null;
    const limit = rawLimit && rawLimit > 0 ? clampNumber(rawLimit, 1, MAX_BUFFER_SIZE) : options.snapshotMeta.limit;

    const receivedAtValue = payloadObject['receivedAt'];
    const receivedAt = typeof receivedAtValue === 'number' && Number.isFinite(receivedAtValue) && receivedAtValue > 0 ? receivedAtValue : Date.now();
    return { entries, source, limit, receivedAt };
};

const normalizeStreamMessage = (payload: JsonValue | null | undefined, type: JsonValue | null | undefined, raw: JsonValue | null | undefined): NormalizedStreamMessage | null => {
    const rawObject = raw && isObject(raw) ? raw : null;
    const typeFromParameter = isString(type) ? type : null;
    const typeFromRaw = rawObject && isString(rawObject['type']) ? rawObject['type'] : null;
    const typeFromPayload = isObject(payload) && isString(payload['type']) ? payload['type'] : null;
    const resolvedType = cleanStr(typeFromParameter) || cleanStr(typeFromRaw) || cleanStr(typeFromPayload) || null;

    if (rawObject && hasOwn(rawObject, 'payload')) {
        const rawPayload = rawObject['payload'];
        return {
            type: resolvedType,
            payload: isJsonObject(rawPayload) ? rawPayload : null
        };
    }

    if (payload && isObject(payload) && hasOwn(payload, 'payload')) {
        const payloadObject = payload;
        const nested = payloadObject['payload'];
        return {
            type: resolvedType || (isString(payloadObject['type']) ? payloadObject['type'] : null),
            payload: isJsonObject(nested) ? nested : null
        };
    }

    if (resolvedType) {
        return {
            type: resolvedType,
            payload: isJsonObject(payload) ? payload : isJsonObject(rawObject) ? rawObject : null
        };
    }

    if (isJsonObject(payload)) {
        return {
            type: isString(payload['type']) ? payload['type'] : null,
            payload
        };
    }

    return payload ? { type: null, payload: null } : null;
};

const isHistoryReplayMode = (mode: string | null): mode is 'history' | 'replay' => {
    if (!mode) {
        return false;
    }
    const normalized = mode.trim().toLowerCase();
    return normalized === 'history' || normalized === 'replay';
};

const normalizeStreamEventType = (value: string | null): string | null => {
    if (!isString(value)) {
        return null;
    }
    return value
        .trim()
        .toLowerCase()
        .replace(/[\s_-]+/g, '');
};

export { isHistoryReplayMode, normalizeStreamEventType, normalizeStreamMessage, resolveSnapshotPayload };
