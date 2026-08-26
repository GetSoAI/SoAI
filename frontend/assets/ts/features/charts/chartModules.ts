/* SoAI - Charts feature chart modules [frontend/assets/ts/features/charts/chartModules.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createChartSession } from '@features/charts/session/createChartSession.ts';
import { buildValueSeriesFromPairs, sanitizePoints } from '@features/charts/datatransforms/actions.ts';
import { DEFAULT_CANDLE_INTERVALS, DEFAULT_TIME_RANGES, ONE_MINUTE_MS } from '@features/charts/datatransforms/constants.ts';
import { buildLineGapFillers, toHeikinAshiSeries, toLineSeries } from '@features/charts/datatransforms/effects.ts';
import { normalizeMinutesList, resolveSupportedIntervalMs } from '@features/charts/datatransforms/guards.ts';
import { formatTimeRangeMinutes } from '@features/charts/timeRangeFormatting.ts';
import { buildCandlestickIntervalSelection, buildTimeRangeSelection, deriveCandlestickIntervals, deriveTimeRangeOptions } from '@features/charts/datatransforms/service.ts';
import { createChartLogger } from '@features/charts/logging.ts';
import { updateRealtimeCandlestick } from '@features/charts/ohlc/actions.ts';
import { resolveNumeric, toTimestampMs } from '@features/charts/ohlc/guards.ts';
import { buildCandlestickSeries, parseBackendOhlcResponse } from '@features/charts/ohlc/service.ts';

const logger = createChartLogger('ChartModules', { defaultLevel: 'debug' });
const ChartDataTransforms = Object.freeze({
    sanitizePoints,
    buildValueSeriesFromPairs,
    formatTimeRangeMinutes,
    deriveTimeRangeOptions,
    deriveCandlestickIntervals,
    normalizeMinutesList,
    resolveSupportedIntervalMs,
    buildTimeRangeSelection,
    buildCandlestickIntervalSelection,
    toLineSeries,
    buildLineGapFillers,
    toHeikinAshiSeries,
    constants: Object.freeze({
        DEFAULT_TIME_RANGES,
        DEFAULT_CANDLE_INTERVALS,
        ONE_MINUTE_MS
    })
});

const ChartOhlc = Object.freeze({
    resolveNumeric,
    toTimestampMs,
    parseBackendOhlcResponse,
    buildCandlestickSeries,
    updateRealtimeCandlestick
});

interface ChartModules {
    createSession: typeof createChartSession;
    data: typeof ChartDataTransforms;
    ohlc: typeof ChartOhlc;
}

interface ChartModulesAccess {
    ensure(): Promise<ChartModules>;
    getSync(): ChartModules;
    reset(): void;
}

const moduleSummary: Readonly<ChartModules> = Object.freeze({
    createSession: createChartSession,
    data: ChartDataTransforms,
    ohlc: ChartOhlc
});

let cachedModules: ChartModules | null = null;
let loggedReady = false;

const logReady = (): void => {
    if (loggedReady) {
        return;
    }
    logger.info('Chart modules ready', {
        exports: Object.keys(moduleSummary),
        runtimeLoaded: true
    });
    loggedReady = true;
};

const resolveModules = (): ChartModules => {
    if (!cachedModules) {
        cachedModules = moduleSummary;
        logReady();
    }
    return cachedModules;
};

const chartModulesAccess: Readonly<ChartModulesAccess> = Object.freeze({
    ensure: async (): Promise<ChartModules> => resolveModules(),
    getSync: (): ChartModules => resolveModules(),
    reset: (): void => {
        cachedModules = null;
        loggedReady = false;
    }
});

export { chartModulesAccess };
export type { ChartModules, ChartModulesAccess };
