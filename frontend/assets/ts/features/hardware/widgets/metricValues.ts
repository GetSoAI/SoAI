/* SoAI - Hardware feature metric values [frontend/assets/ts/features/hardware/widgets/metricValues.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { readPayloadDottedPathValue } from '@core/types/payloadPathReader.ts';
import type { MemoryRaw } from '@features/hardware/models/types.ts';

const MB_IN_BYTES = 1024 * 1024;

interface MemoryValues {
    usedMb: number;
    totalMb: number;
}

const resolveNumericMetric = (source: JsonObject | null | undefined, paths: readonly string[]): number | null => {
    if (!Array.isArray(paths)) return null;
    for (const path of paths) {
        const value = readPayloadDottedPathValue(source, path);
        if (value === undefined) {
            continue;
        }
        if (isFiniteNumber(value)) return value;
        const numeric = Number(value);
        if (isFiniteNumber(numeric)) return numeric;
    }
    return null;
};

const resolveMemoryValuesMb = (source: MemoryRaw | null | undefined): MemoryValues => {
    if (!source) {
        return { usedMb: 0, totalMb: 0 };
    }
    const usedBytes = Number(source.usedBytes);
    const totalBytes = Number(source.totalBytes);
    const usedMb = isFiniteNumber(usedBytes) && usedBytes >= 0 ? usedBytes / MB_IN_BYTES : 0;
    const totalMb = isFiniteNumber(totalBytes) && totalBytes > 0 ? totalBytes / MB_IN_BYTES : 0;
    return { usedMb, totalMb };
};

export { resolveNumericMetric, resolveMemoryValuesMb };
export type { MemoryValues };
