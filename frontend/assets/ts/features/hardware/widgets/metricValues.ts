/* SoAI - Hardware feature metric values [frontend/assets/ts/features/hardware/widgets/metricValues.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareMemorySnapshot } from '@core/api/contracts/hardwareContractTypes.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { readPayloadDottedPathValue } from '@core/types/payloadPathReader.ts';

const MB_IN_BYTES = 1024 * 1024;

interface MemoryValues {
    usedMb?: number | undefined;
    totalMb?: number | undefined;
}

const resolveNumericMetric = (source: JsonObject | null | undefined, paths: readonly string[]): number | null => {
    if (!Array.isArray(paths)) return null;
    for (const path of paths) {
        const value = readPayloadDottedPathValue(source, path);
        if (value === undefined || value === null || typeof value === 'boolean' || (typeof value === 'string' && !value.trim())) {
            continue;
        }
        if (isFiniteNumber(value)) return value;
        const numeric = Number(value);
        if (isFiniteNumber(numeric)) return numeric;
    }
    return null;
};

const resolveMemoryValuesMb = (source: HardwareMemorySnapshot | null | undefined): MemoryValues => {
    const usedMb = isFiniteNumber(source?.usedBytes) && source.usedBytes >= 0 ? source.usedBytes / MB_IN_BYTES : isFiniteNumber(source?.usedGb) && source.usedGb >= 0 ? source.usedGb * 1024 : undefined;
    const totalMb = isFiniteNumber(source?.totalBytes) && source.totalBytes >= 0 ? source.totalBytes / MB_IN_BYTES : isFiniteNumber(source?.totalGb) && source.totalGb >= 0 ? source.totalGb * 1024 : undefined;
    return { usedMb, totalMb };
};

export { resolveNumericMetric, resolveMemoryValuesMb };
export type { MemoryValues };
