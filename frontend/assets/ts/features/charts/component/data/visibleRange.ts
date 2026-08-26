/* SoAI - Charts feature visible range [frontend/assets/ts/features/charts/component/data/visibleRange.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isFunction } from '@core/typeGuards.ts';
import type { ChartOptions, CrosshairState, Dataset, OhlcValues } from '@features/charts/chartTypes.ts';
import { DEFAULT_MAX_DATA_POINTS, DEFAULT_VERTICAL_SCALE_PADDING_RATIO, isFin, MIN_PIXEL_PER_BAR, MIN_VERTICAL_PIXEL_PADDING, MIN_VISIBLE_ZOOM_SLOTS, MIN_ZOOM_LEVEL } from '@features/charts/component/chartComponentStatics.ts';
import type { PanState, Scale, SlotMetrics, TimeRange, VisibleRange, VisibleRangeStats, ZoomState } from '@features/charts/component/chartComponentTypes.ts';
import type { ChartEventDetail } from '@features/charts/component/effects.ts';
import { findValidIndexBackward } from '@features/charts/component/data/interpolation.ts';
import type { AxisCache, ChartDimensions } from '@features/charts/rendering/renderingModels.ts';

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
    baseBarPixelWidth: number;
    zoom: ZoomState;
    pan: PanState;
    lastEmittedTimeRange: TimeRange;
    ohlcScratch: OhlcValues;
}

export interface VisibleRangeCalculationPort {
    chartEmit: (evt: string, data?: ChartEventDetail) => void;
    enforceScaleBounds: () => void;
    getChartDimensions: () => ChartDimensions;
    getEffectiveDataLength: () => number;
    getRenderableOhlcBuffers: () => {
        open: Float64Array;
        high: Float64Array;
        low: Float64Array;
        close: Float64Array;
    } | null;
    getCloseValue: (index: number) => number | undefined;
    getOhlcForIndex: (index: number, target?: OhlcValues | null) => OhlcValues;
}

interface SlotMetricsStatePort {
    chartOptions: ChartOptions;
    baseBarPixelWidth: number;
    zoom: ZoomState;
}

interface SlotMetricsCalculationPort {
    getChartDimensions: () => ChartDimensions;
    getEffectiveDataLength: () => number;
}

const getPixelsPerBarForLevel = (state: SlotMetricsStatePort, calculations: SlotMetricsCalculationPort, level: number | null | undefined): number => {
    const { chartWidth: cw } = calculations.getChartDimensions();
    const minLevel = Math.max(MIN_ZOOM_LEVEL, state.zoom?.minLevel ?? MIN_ZOOM_LEVEL);
    const maxLevel = Math.max(minLevel, state.zoom?.maxLevel ?? minLevel);
    const sl = clampNumber(Math.max(MIN_ZOOM_LEVEL, level ?? state.zoom?.level ?? 1), minLevel, maxLevel);
    const bp = state.baseBarPixelWidth * sl;
    if (!isFin(cw) || cw <= 0) return Math.max(MIN_PIXEL_PER_BAR, bp);
    const rm = state.chartOptions.rightMarginBars || 0;
    const de = calculations.getEffectiveDataLength() || Math.min(512, state.chartOptions.maxDataPoints || DEFAULT_MAX_DATA_POINTS);
    return Math.max(MIN_PIXEL_PER_BAR, bp, cw / Math.max(1, Math.min(state.chartOptions.maxDataPoints || DEFAULT_MAX_DATA_POINTS, de + Math.max(4, rm))));
};

const getPixelsPerBar = (state: SlotMetricsStatePort, calculations: SlotMetricsCalculationPort): number => getPixelsPerBarForLevel(state, calculations, state.zoom.level);

const getSlotMetricsForLevel = (state: SlotMetricsStatePort, calculations: SlotMetricsCalculationPort, level: number | null | undefined): SlotMetrics => {
    const { chartWidth: cw } = calculations.getChartDimensions();
    if (cw <= 0) return { totalSlots: 1, dataSlots: 1, marginSlots: 0 };
    const pb = getPixelsPerBarForLevel(state, calculations, level);
    const rm = state.chartOptions.rightMarginBars || 0;
    const cap = Math.max(rm + 1, Math.min(state.chartOptions.maxDataPoints, (calculations.getEffectiveDataLength() || 0) + Math.max(4, rm)));
    const minimumDataSlots = Math.max(1, Math.min(cap, MIN_VISIBLE_ZOOM_SLOTS, calculations.getEffectiveDataLength() || MIN_VISIBLE_ZOOM_SLOTS));
    const ts = clampNumber(Math.round(cw / pb), minimumDataSlots, cap);
    let ms = Math.min(ts - 1, rm, Math.floor(ts * state.chartOptions.maxRightMarginRatio), Math.floor(state.chartOptions.maxRightMarginPx / pb));
    ms = Math.max(0, ms);
    if (ts - ms < minimumDataSlots) {
        ms = Math.max(0, ts - minimumDataSlots);
    }
    if (rm > 0 && ms === 0 && ts > minimumDataSlots) ms = 1;
    return { totalSlots: ts, dataSlots: Math.max(1, ts - ms), marginSlots: ms };
};

const getSlotMetrics = (state: SlotMetricsStatePort, calculations: SlotMetricsCalculationPort): SlotMetrics => getSlotMetricsForLevel(state, calculations, state.zoom.level);

const getMaxOffsetForMetrics = (state: SlotMetricsStatePort, calculations: SlotMetricsCalculationPort, metrics: SlotMetrics | null | undefined = null): number => {
    const dataSlotsValue = metrics?.dataSlots ?? null;
    const dataSlots = typeof dataSlotsValue === 'number' && isFin(dataSlotsValue) ? dataSlotsValue : getSlotMetrics(state, calculations).dataSlots;
    return Math.max(0, Math.max(0, calculations.getEffectiveDataLength()) - dataSlots);
};

const updateVisibleRange = (chart: VisibleRangeStatePort, calculations: VisibleRangeCalculationPort): void => {
    const match = getSlotMetrics(chart, calculations);
    const { dataSlots: ds } = match;
    const stringValue = Math.max(0, Math.floor(chart.pan.offset));
    chart.visibleRange = {
        start: stringValue,
        end: Math.min(calculations.getEffectiveDataLength(), stringValue + ds),
        displayCount: ds,
        offsetFraction: ds > 1 ? clampNumber(chart.pan.offset - stringValue, 0, 0.999999) : 0,
        ...match
    };
    const startIndex = chart.visibleRange.start;
    const endIndex = chart.visibleRange.end;
    if (chart.dataLength === 0) return;
    const clampedStart = clampNumber(startIndex, 0, chart.dataLength - 1);
    const clampedEnd = clampNumber(endIndex - 1, 0, chart.dataLength - 1);
    const st = chart.timestamps[clampedStart] ?? null;
    const et = chart.timestamps[clampedEnd] ?? null;
    if (st === null || et === null) return;
    const last = chart.lastEmittedTimeRange || {};
    if (startIndex === last.start && endIndex === last.end && st === last.startTs && et === last.endTs) return;
    calculations.chartEmit('timeRangeChange', { start: st, end: et });
    chart.chartOptions.onTimeRangeChange?.(st, et);
    chart.lastEmittedTimeRange = { start: startIndex, end: endIndex, startTs: st, endTs: et };
};

const updateVisibleRangeStats = (chart: VisibleRangeStatePort, calculations: VisibleRangeCalculationPort): void => {
    const { start, displayCount } = chart.visibleRange;
    const re = Math.min(chart.dataLength, start + displayCount);
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
        if (requestPos && !(objectValue > 0 && leftValue > 0 && height > 0 && candidateValue > 0)) continue;
        if (isFin(leftValue)) pMin = pMin === null ? leftValue : Math.min(pMin, leftValue);
        if (isFin(height)) pMax = pMax === null ? height : Math.max(pMax, height);
        if (isFin(candidateValue)) {
            pSum += candidateValue;
            pCount++;
        }
    }

    if (isArray(chart.datasets) && chart.datasets.length) {
        for (const dataValue of chart.datasets) {
            const dv = dataValue?.values;
            if (!dv) continue;
            const len = isFin(dv.length) ? Number(dv.length) : 0;
            if (!len) continue;
            const up = Math.min(len, start + displayCount);
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

const updateScale = (chart: VisibleRangeStatePort, calculations: VisibleRangeCalculationPort): void => {
    if (chart.visibleRangeStats.count === 0) {
        if (chart.scale.auto) {
            chart.scale.min = null;
            chart.scale.max = null;
        }
        return;
    }
    if (!chart.scale.auto) return;
    const statMin = chart.visibleRangeStats.min;
    const statMax = chart.visibleRangeStats.max;
    if (statMin === null || statMax === null) return;
    let min: number = statMin;
    let max: number = statMax;
    const pr = isFin(chart.chartOptions.verticalPaddingRatio) ? chart.chartOptions.verticalPaddingRatio : DEFAULT_VERTICAL_SCALE_PADDING_RATIO;
    const ch = Math.max(0, (isFunction(calculations.getChartDimensions) ? calculations.getChartDimensions() : null)?.chartHeight || 0);
    const mp = ch > 0 ? Math.max(0, MIN_VERTICAL_PIXEL_PADDING) : 0;

    if (chart.chartOptions.scaleType === 'logarithmic') {
        min = Math.max(min, 1e-9);
        max = Math.max(max, min * 1.01);
        const lMin = Math.log10(min);
        const lMax = Math.log10(max);
        const lr = Math.max(lMax - lMin, 1e-6);
        let match = Math.max(lr * (pr > 0 ? pr : DEFAULT_VERTICAL_SCALE_PADDING_RATIO), 1e-6);
        if (lr > 0 && mp > 0 && ch > 0) match = Math.max(match, (lr / ch) * mp);
        chart.scale.min = 10 ** (lMin - match);
        chart.scale.max = 10 ** (lMax + match);
    } else {
        const redChannel = max - min;
        const mag = redChannel > 0 ? redChannel : Math.max(Math.abs(min), Math.abs(max), 1);
        let match = mag * (pr > 0 ? pr : DEFAULT_VERTICAL_SCALE_PADDING_RATIO);
        if (redChannel > 0 && mp > 0 && ch > 0) match = Math.max(match, (redChannel / ch) * mp);
        chart.scale.min = min - match;
        chart.scale.max = max + match;
    }
    calculations.enforceScaleBounds();
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

export { formatValue, getMaxOffsetForMetrics, getPixelsPerBar, getPixelsPerBarForLevel, getSlotMetrics, getSlotMetricsForLevel, resolveValuePrecision, updateLegendData, updateScale, updateVisibleRange, updateVisibleRangeStats, valueToPixel };
