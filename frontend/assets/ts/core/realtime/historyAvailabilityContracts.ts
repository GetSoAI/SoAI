/* SoAI - Frontend history sample availability V1 contracts [frontend/assets/ts/core/realtime/historyAvailabilityContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasOwn } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { readNullableFiniteIntegerValue, readRequiredFiniteIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';

interface HistoryAvailability {
    oldestSampleTsMs: number | null;
    newestSampleTsMs: number | null;
    observedAtMs: number;
}

const AVAILABILITY_KEYS = ['oldest_sample_ts_ms', 'newest_sample_ts_ms', 'observed_at_ms'];

const decodeOptionalHistoryAvailability = (metadata: JsonObject, label: string): HistoryAvailability | null => {
    if (!hasOwn(metadata, 'availability')) return null;
    const availabilityLabel = `${label}.availability`;
    const record = requireRecord(metadata['availability'], availabilityLabel);
    for (const key of AVAILABILITY_KEYS) {
        if (!hasOwn(record, key)) throw new TypeError(`${availabilityLabel}.${key} is required`);
    }
    const oldestSampleTsMs = readNullableFiniteIntegerValue(record['oldest_sample_ts_ms'], `${availabilityLabel}.oldest_sample_ts_ms`);
    const newestSampleTsMs = readNullableFiniteIntegerValue(record['newest_sample_ts_ms'], `${availabilityLabel}.newest_sample_ts_ms`);
    if ((oldestSampleTsMs === null) !== (newestSampleTsMs === null) || (oldestSampleTsMs !== null && newestSampleTsMs !== null && oldestSampleTsMs > newestSampleTsMs)) {
        throw new TypeError(`${availabilityLabel} sample bounds are inconsistent`);
    }
    return {
        oldestSampleTsMs,
        newestSampleTsMs,
        observedAtMs: readRequiredFiniteIntegerValue(record['observed_at_ms'], `${availabilityLabel}.observed_at_ms`)
    };
};

export { decodeOptionalHistoryAvailability };
export type { HistoryAvailability };
