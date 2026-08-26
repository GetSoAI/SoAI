/* SoAI - Charts feature chart type normalization [frontend/assets/ts/features/charts/chartTypeNormalization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';

const normalizeChartTypeToken = (chartType: JsonValue | null | undefined): string | null => {
    if (!isString(chartType)) {
        return null;
    }
    const normalized = chartType.trim().toLowerCase().replace(/\s+/g, '-');
    if (normalized === 'heikin' || normalized === 'heikinashi') {
        return 'heikin-ashi';
    }
    return normalized;
};

const isOhlcChartType = (chartType: JsonValue | null | undefined): boolean => {
    const normalized = normalizeChartTypeToken(chartType);
    return normalized === 'candlestick' || normalized === 'ohlcbars' || normalized === 'heikin-ashi';
};

export { isOhlcChartType, normalizeChartTypeToken };
