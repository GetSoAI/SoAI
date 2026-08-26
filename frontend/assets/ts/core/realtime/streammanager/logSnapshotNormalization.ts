/* SoAI - Shared realtime log snapshot normalization [frontend/assets/ts/core/realtime/streammanager/logSnapshotNormalization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { LogSnapshotResult } from '@core/realtime/streammanager/types.ts';
import { telemetry } from '@core/telemetry/service.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isFiniteNumber, isObject } from '@core/typeGuards.ts';

const DEFAULT_LOG_SNAPSHOT_SOURCE = 'core';
const DEFAULT_LOG_SNAPSHOT_LIMIT = 500;
const MAX_LOG_SNAPSHOT_LIMIT = 5000;

const resolveLogSource = (candidate: JsonValue | null | undefined): string => toTrimmedString(candidate) || DEFAULT_LOG_SNAPSHOT_SOURCE;

const resolveLogLimit = (candidate: JsonValue | null | undefined): number => clampNumber(isFiniteNumber(candidate) ? Math.floor(candidate) : DEFAULT_LOG_SNAPSHOT_LIMIT, 1, MAX_LOG_SNAPSHOT_LIMIT);

const resolveRemoteTimestampMs = (raw: JsonValue | null | undefined): number | null => {
    if (!isObject(raw)) return null;
    const tsMs = raw['timestamp_ms'];
    if (!isFiniteNumber(tsMs)) return null;
    return Number.isFinite(tsMs) ? tsMs : null;
};

const normalizeLogSnapshot = (data: JsonValue | null | undefined, receivedAtMs?: number): LogSnapshotResult => {
    if (!isObject(data)) throw new Error('Invalid log snapshot');
    const snapshot = data;
    const rawEntries = snapshot['entries'];
    if (!isArray(rawEntries)) throw new Error('Missing entries');
    const entries = rawEntries
        .map((entry: JsonValue | null | undefined) => {
            if (!isJsonObject(entry)) return null;
            const normalizedEntry: JsonObject = {};
            for (const [key, value] of Object.entries(entry)) {
                normalizedEntry[key] = value;
            }
            return normalizedEntry;
        })
        .filter((entry): entry is LogSnapshotResult['entries'][number] => entry !== null);
    const source = resolveLogSource(snapshot['source']);
    const limit = resolveLogLimit(snapshot['limit']);
    telemetry.publishMetric('logs.snapshot.entries', entries.length, { source, limit });
    return { entries, source, limit, receivedAt: isFiniteNumber(receivedAtMs) ? receivedAtMs : Date.now() };
};

export { DEFAULT_LOG_SNAPSHOT_LIMIT, DEFAULT_LOG_SNAPSHOT_SOURCE, MAX_LOG_SNAPSHOT_LIMIT, normalizeLogSnapshot, resolveLogLimit, resolveLogSource, resolveRemoteTimestampMs };
