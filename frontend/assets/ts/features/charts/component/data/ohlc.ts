/* SoAI - Chart component OHLC data management [frontend/assets/ts/features/charts/component/data/ohlc.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isArray, isObject } from '@core/typeGuards.ts';
import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import type { ChartOptions, OhlcValues } from '@features/charts/chartTypes.ts';
import { isOhlcChartType } from '@features/charts/chartTypeNormalization.ts';
import { isFin } from '@features/charts/component/chartComponentStatics.ts';
import type { OhlcData } from '@features/charts/component/chartComponentTypes.ts';
import type { ChartPointCandidate, NormalizedDataPoint } from '@features/charts/data/chartPointTypes.ts';

interface OhlcHost {
    chartOptions: ChartOptions;
    dataLength: number;
    datasets: { values?: Float64Array | number[] | undefined }[];
    dataStructure: string;
    sourceSeriesMode: string;
    values: Float64Array;

    ohlc: OhlcData | null;
    heikin: OhlcData | null;
    heikinDirtyIndex: number;
    heikinValidLength: number;
}

const hasOhlcData = (chart: OhlcHost): boolean => chart.dataStructure === 'ohlc' && chart.ohlc?.open !== undefined;

const ensureOhlcStorage = (chart: OhlcHost): OhlcData => {
    if (!chart.ohlc || chart.ohlc.open?.length !== chart.chartOptions.maxDataPoints) {
        chart.ohlc = {
            open: new Float64Array(chart.chartOptions.maxDataPoints),
            high: new Float64Array(chart.chartOptions.maxDataPoints),
            low: new Float64Array(chart.chartOptions.maxDataPoints),
            close: new Float64Array(chart.chartOptions.maxDataPoints)
        };
    }
    return chart.ohlc;
};

const discardHeikin = (chart: OhlcHost): void => {
    chart.heikin = null;
    chart.heikinDirtyIndex = 0;
    chart.heikinValidLength = 0;
};

const supportsDerivedHeikin = (chart: OhlcHost): boolean => hasOhlcData(chart);

const ensureHeikinStorage = (chart: OhlcHost): OhlcData | null => {
    if (!supportsDerivedHeikin(chart)) {
        discardHeikin(chart);
        return null;
    }
    if (!chart.heikin || chart.heikin.open?.length !== chart.chartOptions.maxDataPoints) {
        chart.heikin = {
            open: new Float64Array(chart.chartOptions.maxDataPoints),
            high: new Float64Array(chart.chartOptions.maxDataPoints),
            low: new Float64Array(chart.chartOptions.maxDataPoints),
            close: new Float64Array(chart.chartOptions.maxDataPoints)
        };
        chart.heikinDirtyIndex = 0;
        chart.heikinValidLength = 0;
    }
    return chart.heikin;
};

const invalidateHeikinFrom = (chart: OhlcHost, index: number = 0): void => {
    if (!supportsDerivedHeikin(chart)) {
        discardHeikin(chart);
        return;
    }
    const currentTime = clampNumber(Math.floor(index), 0, chart.dataLength - 1);
    chart.heikinDirtyIndex = Math.min(chart.heikinDirtyIndex ?? currentTime, currentTime);
    chart.heikinValidLength = Math.min(chart.heikinValidLength ?? currentTime, chart.heikinDirtyIndex);
};

const ensureHeikinComputed = (chart: OhlcHost): OhlcData | null => {
    if (chart.chartOptions.chartType !== 'heikin-ashi' || !supportsDerivedHeikin(chart) || chart.sourceSeriesMode === 'heikin-ashi') {
        return chart.ohlc;
    }

    const heikin = ensureHeikinStorage(chart);
    const source = chart.ohlc;
    const len = chart.dataLength;
    if (!heikin || !source || len <= 0) {
        chart.heikinValidLength = 0;
        chart.heikinDirtyIndex = 0;
        return source;
    }

    const from = Math.max(0, chart.heikinDirtyIndex - 1);
    if (from >= len) return heikin;

    const { open: sourceOpen, high: sourceHigh, low: sourceLow, close: sourceClose } = source;
    const { open: heikinOpen, high: heikinHigh, low: heikinLow, close: heikinClose } = heikin;

    let prevOpen = from > 0 ? (heikinOpen[from - 1] ?? Number.NaN) : Number.NaN;
    let prevClose = from > 0 ? (heikinClose[from - 1] ?? Number.NaN) : Number.NaN;
    for (let index = from; index < len; index++) {
        const objectValue = sourceOpen[index] ?? Number.NaN;
        const hi = sourceHigh[index] ?? Number.NaN;
        const lo = sourceLow[index] ?? Number.NaN;
        const candidateValue = sourceClose[index] ?? Number.NaN;
        if (!(isFin(objectValue) && isFin(hi) && isFin(lo) && isFin(candidateValue))) {
            heikinOpen[index] = heikinHigh[index] = heikinLow[index] = heikinClose[index] = Number.NaN;
            prevOpen = prevClose = Number.NaN;
            continue;
        }

        const heikinAverageClose = (objectValue + hi + lo + candidateValue) / 4;
        const heikinAverageOpen = index === 0 || !isFin(prevOpen) ? (objectValue + candidateValue) / 2 : (prevOpen + prevClose) / 2;

        heikinOpen[index] = heikinAverageOpen;
        heikinHigh[index] = Math.max(hi, heikinAverageOpen, heikinAverageClose);
        heikinLow[index] = Math.min(lo, heikinAverageOpen, heikinAverageClose);
        heikinClose[index] = heikinAverageClose;
        prevOpen = heikinAverageOpen;
        prevClose = heikinAverageClose;
    }

    chart.heikinValidLength = len;
    chart.heikinDirtyIndex = len;
    return heikin;
};

const getRenderableOhlcBuffers = (chart: OhlcHost): OhlcData | null => {
    if (!hasOhlcData(chart)) return null;
    return chart.chartOptions.chartType === 'heikin-ashi' ? ensureHeikinComputed(chart) : chart.ohlc;
};

const getValueBufferForRendering = (chart: OhlcHost): Float64Array => {
    const buffers = chart.chartOptions.chartType === 'heikin-ashi' ? getRenderableOhlcBuffers(chart) : null;
    return buffers?.close || chart.values;
};

const getEffectiveDataLength = (chart: OhlcHost): number => {
    if (chart.dataLength > 0) return chart.dataLength;
    if (!isArray(chart.datasets)) return 0;
    let overlayLength = 0;
    for (const dataset of chart.datasets) {
        const values = dataset?.values;
        const len = values && isFin(values.length) ? Number(values.length) : 0;
        if (isFin(len)) overlayLength = Math.max(overlayLength, len);
    }
    return overlayLength;
};

const isOhlcRenderingType = (chart: OhlcHost, type: string = chart.chartOptions.chartType): boolean => isOhlcChartType(type || chart.chartOptions.chartType);

const upgradeToOhlc = (chart: OhlcHost): void => {
    if (chart.dataStructure === 'ohlc') return;
    const ohlc = ensureOhlcStorage(chart);
    for (let index = 0; index < chart.dataLength; index++) {
        const value = chart.values[index] ?? Number.NaN;
        ohlc.open[index] = ohlc.high[index] = ohlc.low[index] = ohlc.close[index] = isFin(value) ? value : 0;
    }
    chart.dataStructure = 'ohlc';
    if (chart.sourceSeriesMode !== 'heikin-ashi') chart.sourceSeriesMode = 'ohlc';
    invalidateHeikinFrom(chart, 0);
};

const downgradeToValue = (chart: OhlcHost): void => {
    chart.dataStructure = 'value';
    chart.ohlc = null;
    discardHeikin(chart);
    chart.sourceSeriesMode = 'value';
};

const isOhlcPoint = (point: ChartPointCandidate): boolean => {
    if (!isObject(point)) return false;
    if (!('open' in point) || !('high' in point) || !('low' in point) || !('close' in point)) return false;
    return isFin(point['open']) && isFin(point['high']) && isFin(point['low']) && isFin(point['close']);
};

const normalizeDataPoint = (point: ChartPointCandidate): NormalizedDataPoint | null => {
    if (!isObject(point)) return null;
    const timestamp = readRuntimeFiniteNumberOrFallbackValue(point['timestamp'], null);
    if (timestamp === null) return null;

    const valueCandidate = point['value'] ?? ('close' in point ? point['close'] : undefined);
    const value = readRuntimeFiniteNumberOrFallbackValue(valueCandidate ?? null, null);
    if (value === null) return null;

    const sourceRaw = String(point['sourceMode'] ?? '')
        .trim()
        .toLowerCase();
    const modeRaw = String(point['mode'] ?? '')
        .trim()
        .toLowerCase();
    const isHeikin = ['heikin-ashi', 'heikinashi', 'heikin'].includes(sourceRaw) || ['heikin-ashi', 'heikinashi', 'heikin'].includes(modeRaw);
    const isOhlcMode = isHeikin || sourceRaw === 'ohlc' || modeRaw === 'ohlc' || isOhlcPoint(point);

    let open = value;
    let high = value;
    let low = value;
    let close = value;
    if (isOhlcMode) {
        if (!('open' in point) || !('high' in point) || !('low' in point) || !('close' in point)) {
            return null;
        }
        const openNumber = readRuntimeFiniteNumberOrFallbackValue(point['open'], null);
        const highNumber = readRuntimeFiniteNumberOrFallbackValue(point['high'], null);
        const lowNumber = readRuntimeFiniteNumberOrFallbackValue(point['low'], null);
        const closeNumber = readRuntimeFiniteNumberOrFallbackValue(point['close'], null);
        if (openNumber === null || highNumber === null || lowNumber === null || closeNumber === null) {
            return null;
        }
        open = openNumber;
        high = highNumber;
        low = lowNumber;
        close = closeNumber;
    }

    return {
        mode: isOhlcMode ? 'ohlc' : 'value',
        sourceMode: isHeikin ? 'heikin-ashi' : isOhlcMode ? 'ohlc' : 'value',
        timestamp,
        value,
        open,
        high,
        low,
        close
    };
};

const getOpenValue = (chart: OhlcHost, index: number): number | undefined => {
    return getRenderableOhlcBuffers(chart)?.open[index] ?? chart.values[index];
};

const getHighValue = (chart: OhlcHost, index: number): number | undefined => {
    return getRenderableOhlcBuffers(chart)?.high[index] ?? chart.values[index];
};

const getLowValue = (chart: OhlcHost, index: number): number | undefined => {
    return getRenderableOhlcBuffers(chart)?.low[index] ?? chart.values[index];
};

const getCloseValue = (chart: OhlcHost, index: number): number | undefined => {
    return getRenderableOhlcBuffers(chart)?.close[index] ?? chart.values[index];
};

const getOhlcForIndex = (chart: OhlcHost, index: number, target: OhlcValues | null = null): OhlcValues => {
    const ohlc: OhlcValues = target ?? { open: null, high: null, low: null, close: null };
    if (!isFin(index) || index < 0 || index >= chart.dataLength) {
        ohlc.open = ohlc.high = ohlc.low = ohlc.close = null;
        return ohlc;
    }
    const resolvedIndex = index;
    const buffers = getRenderableOhlcBuffers(chart);
    if (buffers) {
        ohlc.open = buffers.open[resolvedIndex] ?? null;
        ohlc.high = buffers.high[resolvedIndex] ?? null;
        ohlc.low = buffers.low[resolvedIndex] ?? null;
        ohlc.close = buffers.close[resolvedIndex] ?? null;
    } else {
        const value = isFin(chart.values[resolvedIndex]) ? chart.values[resolvedIndex] : null;
        ohlc.open = ohlc.high = ohlc.low = ohlc.close = value ?? null;
    }
    return ohlc;
};

export { discardHeikin, downgradeToValue, ensureHeikinComputed, ensureHeikinStorage, ensureOhlcStorage, getCloseValue, getEffectiveDataLength, getHighValue, getLowValue, getOhlcForIndex, getOpenValue, getRenderableOhlcBuffers, getValueBufferForRendering, hasOhlcData, invalidateHeikinFrom, isOhlcPoint, isOhlcRenderingType, normalizeDataPoint, supportsDerivedHeikin, upgradeToOhlc };
