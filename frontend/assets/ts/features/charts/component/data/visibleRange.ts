/* SoAI - Charts feature visible range [frontend/assets/ts/features/charts/component/data/visibleRange.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isFunction } from '@core/typeGuards.ts';
import type { ChartOptions, CrosshairState, Dataset, OhlcValues } from '@features/charts/chartTypes.ts';
import { isFin } from '@features/charts/component/chartComponentStatics.ts';
import type { Scale, TimeRange, VisibleRange, VisibleRangeStats } from '@features/charts/component/chartComponentTypes.ts';
import type { ChartEventDetail } from '@features/charts/component/effects.ts';
import { findValidIndexBackward } from '@features/charts/component/data/interpolation.ts';
import { findFirstIndexAtOrAfter, findLastIndexAtOrBefore } from '@features/charts/component/data/timestampIndex.ts';
import { isPlottedOhlc, isPlottedValue } from '@features/charts/rendering/series/guards.ts';
import type { AxisCache, ChartDimensions, RenderGeometry } from '@features/charts/rendering/renderingModels.ts';

interface VisibleRangeStatePort {
    chartOptions: ChartOptions;
    dataLength: number;
    datasets: Dataset[];
    timestamps: Float64Array;
    values: Float64Array;
    crosshair: CrosshairState;
    legendData: Record<string, JsonValue | null | undefined>;
    visibleRange: VisibleRange;
    visibleRangeStats: VisibleRangeStats;
    scale: Scale;
    axisCache: AxisCache | null;
    lastEmittedTimeRange: TimeRange;
    ohlcScratch: OhlcValues;
}

export interface VisibleRangeCalculationPort {
    chartEmit: (evt: string, data?: ChartEventDetail) => void;
    enforceScaleBounds: () => void;
    getChartDimensions: () => ChartDimensions;
    getRenderGeometry: () => RenderGeometry | null;
    getRenderableOhlcBuffers: () => {
        open: Float64Array;
        high: Float64Array;
        low: Float64Array;
        close: Float64Array;
    } | null;
    getCloseValue: (index: number) => number | undefined;
    getOhlcForIndex: (index: number, target?: OhlcValues | null) => OhlcValues;
}

const EMPTY_VISIBLE_RANGE: Readonly<VisibleRange> = Object.freeze({ start: 0, end: 0, startTs: Number.NaN, endTs: Number.NaN });

const resolveRenderIndexRange = (visibleRange: VisibleRange, dataLength: number): { from: number; to: number } => ({ from: Math.max(0, Math.min(visibleRange.start, dataLength) - 1), to: Math.min(dataLength, visibleRange.end + 1) });

const resolveVisibleSegmentIndexRange = (visibleRange: VisibleRange, dataLength: number): { from: number; to: number } => {
    const from = Math.max(0, Math.min(visibleRange.start, dataLength));
    const to = Math.max(from, Math.min(visibleRange.end, dataLength));
    if (from !== to || from === 0 || from === dataLength) return { from, to };
    return { from: from - 1, to: to + 1 };
};

const emitVisibleTimeRange = (chart: VisibleRangeStatePort, calculations: VisibleRangeCalculationPort, startTs: number, endTs: number): void => {
    const last = chart.lastEmittedTimeRange;
    if (startTs === last.startTs && endTs === last.endTs) return;
    chart.lastEmittedTimeRange = { startTs, endTs };
    calculations.chartEmit('timeRangeChange', { start: startTs, end: endTs });
    chart.chartOptions.onTimeRangeChange?.(startTs, endTs);
};

const updateVisibleRange = (chart: VisibleRangeStatePort, calculations: VisibleRangeCalculationPort): void => {
    const geometry = calculations.getRenderGeometry();
    if (!geometry || chart.dataLength === 0) {
        chart.visibleRange = { ...EMPTY_VISIBLE_RANGE };
        return;
    }
    const first = findFirstIndexAtOrAfter(chart.timestamps, chart.dataLength, geometry.startTs);
    const start = first === -1 ? chart.dataLength : first;
    const end = Math.max(start, findLastIndexAtOrBefore(chart.timestamps, chart.dataLength, geometry.endTs) + 1);
    chart.visibleRange = { start, end, startTs: geometry.startTs, endTs: geometry.endTs };
    emitVisibleTimeRange(chart, calculations, geometry.startTs, geometry.endTs);
    chart.chartOptions.history?.demand(geometry.startTs, geometry.endTs);
};

const updateVisibleRangeStats = (chart: VisibleRangeStatePort, calculations: VisibleRangeCalculationPort): void => {
    const { from: start, to: re } = resolveVisibleSegmentIndexRange(chart.visibleRange, chart.dataLength);
    const requestPos = chart.chartOptions.scaleType === 'logarithmic';
    const buffs = calculations.getRenderableOhlcBuffers();
    const bo = buffs ? buffs.open : undefined;
    const bh = buffs ? buffs.high : undefined;
    const bl = buffs ? buffs.low : undefined;
    const bc = buffs ? buffs.close : undefined;
    const vals = chart.values;

    let pMin = null;
    let pMax = null;
    let pSum = 0;
    let pCount = 0;
    let oMin = null;
    let oMax = null;
    let oSum = 0;
    let oCount = 0;

    for (let index = start; index < re; index++) {
        const objectValue = bo ? (bo[index] ?? Number.NaN) : (vals[index] ?? Number.NaN);
        const leftValue = bl ? (bl[index] ?? Number.NaN) : (vals[index] ?? Number.NaN);
        const height = bh ? (bh[index] ?? Number.NaN) : (vals[index] ?? Number.NaN);
        const candidateValue = bc ? (bc[index] ?? Number.NaN) : (vals[index] ?? Number.NaN);
        if (bo ? !isPlottedOhlc(objectValue, height, leftValue, candidateValue, requestPos) : !isPlottedValue(candidateValue, requestPos)) continue;
        pMin = pMin === null ? leftValue : Math.min(pMin, leftValue);
        pMax = pMax === null ? height : Math.max(pMax, height);
        pSum += candidateValue;
        pCount++;
    }

    if (isArray(chart.datasets) && chart.datasets.length) {
        for (const dataValue of chart.datasets) {
            const dv = dataValue?.values;
            if (!dv) continue;
            const len = isFin(dv.length) ? Number(dv.length) : 0;
            if (!len) continue;
            const up = Math.min(len, re);
            for (let index = start; index < up; index++) {
                const value = dv[index] ?? Number.NaN;
                if (!isFin(value) || (requestPos && !(value > 0))) continue;
                oMin = oMin === null ? value : Math.min(oMin, value);
                oMax = oMax === null ? value : Math.max(oMax, value);
                oSum += value;
                oCount++;
            }
        }
    }

    const useOvr = pCount === 0 && oCount > 0;
    chart.visibleRangeStats = {
        min: pMin !== null && oMin !== null ? Math.min(pMin, oMin) : (pMin ?? oMin),
        max: pMax !== null && oMax !== null ? Math.max(pMax, oMax) : (pMax ?? oMax),
        sum: useOvr ? oSum : pSum,
        count: useOvr ? oCount : pCount
    };
};

const updateLegendData = (chart: VisibleRangeStatePort, calculations: VisibleRangeCalculationPort): void => {
    if (chart.dataLength === 0) {
        chart.legendData = {};
        return;
    }
    const rawIndex = chart.crosshair.rawIndex;
    const xo = chart.crosshair.visible && isFin(rawIndex);
    const rawIndexNumber = rawIndex ?? 0;
    let di = clampNumber(xo ? Math.round(rawIndexNumber) : chart.dataLength - 1, 0, chart.dataLength - 1);
    let cv = xo && isFin(chart.crosshair.value) ? chart.crosshair.value : calculations.getCloseValue(di);
    let ts: number | null | undefined = xo ? chart.crosshair.timestamp : (chart.timestamps[di] ?? null);
    let eff = di;
    if (!isFin(cv)) {
        eff = findValidIndexBackward({ timestamps: chart.timestamps, getCloseValue: calculations.getCloseValue }, di, 0);
        if (eff !== -1) {
            cv = calculations.getCloseValue(eff);
            ts = chart.timestamps[eff] ?? null;
        }
    }
    const od = calculations.getOhlcForIndex(xo ? clampNumber(Math.round(rawIndexNumber), 0, chart.dataLength - 1) : eff, chart.ohlcScratch);
    const { min, max, sum, count } = chart.visibleRangeStats;
    const avg = count > 0 ? sum / count : null;
    const pd = xo ? Math.max(0, Math.floor(rawIndexNumber) - 1) : Math.max(0, eff - 1);
    const pv = calculations.getCloseValue(pd);
    const pvNumber = pv ?? Number.NaN;
    const cvNumber = cv ?? Number.NaN;
    const delta = isFin(cvNumber) && isFin(pvNumber) ? cvNumber - pvNumber : null;
    let stringValue: string | null = null;
    if (chart.chartOptions.statusThresholds && isFin(cvNumber)) {
        const { red: redChannel, yellow: yCoordinate } = chart.chartOptions.statusThresholds;
        stringValue = redChannel !== undefined && cvNumber >= redChannel ? 'red' : yCoordinate !== undefined && cvNumber >= yCoordinate ? 'yellow' : 'green';
    }
    chart.legendData = {
        value: cv,
        min,
        max,
        avg,
        baseline: avg,
        timestamp: ts,
        delta,
        status: stringValue,
        open: xo && isFin(chart.crosshair.open) ? chart.crosshair.open : od.open,
        high: xo && isFin(chart.crosshair.high) ? chart.crosshair.high : od.high,
        low: xo && isFin(chart.crosshair.low) ? chart.crosshair.low : od.low,
        close: xo && isFin(chart.crosshair.close) ? chart.crosshair.close : od.close
    };
};

interface ValuePresentationHost {
    chartOptions: ChartOptions;
    scale: Scale;
    axisCache: AxisCache | null;
}

const valueToPixel = (chart: ValuePresentationHost, value: number, height: number, currentTime: number): number => {
    if (chart.chartOptions.scaleType === 'logarithmic' && (!isFin(value) || value <= 0)) return Number.NaN;
    const { min, max } = chart.scale;
    if (min === null || max === null) return currentTime + height / 2;
    const count = chart.chartOptions.scaleType === 'logarithmic' ? (Math.log10(Math.max(value, min)) - Math.log10(min)) / (Math.log10(max) - Math.log10(min) || 1) : (value - min) / (max - min || 1);
    return currentTime + height - count * height;
};

const resolveValuePrecision = (chart: ValuePresentationHost): number => {
    const configuredPrecision = chart.chartOptions.valuePrecision;
    if (typeof configuredPrecision === 'number' && isFin(configuredPrecision)) return configuredPrecision;
    const { min, max } = chart.scale;
    if (!isFin(min) || !isFin(max) || min === null || max === null) return 2;
    const redChannel = Math.abs(max - min);
    if (!redChannel) return 4;
    const stringValue = redChannel / Math.max(1, (chart.axisCache?.yTicks?.length || 5) - 1);
    return !stringValue ? 4 : clampNumber(Math.ceil(-Math.log10(stringValue)), 0, 8);
};

const formatValue = (chart: ValuePresentationHost, value: number): string => {
    return !isFin(value) ? '—' : isFunction(chart.chartOptions.valueFormatter) ? chart.chartOptions.valueFormatter(value) : value.toFixed(resolveValuePrecision(chart) ?? 2);
};

export { EMPTY_VISIBLE_RANGE, formatValue, resolveRenderIndexRange, resolveValuePrecision, resolveVisibleSegmentIndexRange, updateLegendData, updateVisibleRange, updateVisibleRangeStats, valueToPixel };
