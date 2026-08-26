/* SoAI - Metrics page control layer constants [frontend/assets/ts/pages/metrics/controllers/page/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';

const normalizeMetricsIntValue = (value: number, min = 1): number => {
    const normalizedValue = readRuntimeFiniteNumberOrFallbackValue(value, Number.NaN);
    if (!Number.isFinite(normalizedValue)) {
        return min;
    }
    return Math.max(min, Math.round(normalizedValue));
};

export { normalizeMetricsIntValue };
