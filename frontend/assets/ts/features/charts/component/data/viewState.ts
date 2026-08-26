/* SoAI - Charts feature view state [frontend/assets/ts/features/charts/component/data/viewState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isObject, isPlainObject } from '@core/typeGuards.ts';
import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import type { OhlcValues } from '@features/charts/chartTypes.ts';
import { isFin } from '@features/charts/component/chartComponentStatics.ts';
import type { SlotMetrics } from '@features/charts/component/chartComponentTypes.ts';

interface ViewStateHost {
    dataLength: number;
    timestamps: Float64Array;
    scale: { auto: boolean; min: number | null; max: number | null };
    zoom: { level: number; targetLevel: number; minLevel: number; maxLevel: number; isAnimating: boolean };
    pan: {
        offset: number;
        targetOffset: number;
        startOffset: number;
        velocity: number;
        isZooming: boolean;
        isAtTail: boolean;
    };
    crosshair: {
        visible: boolean;
        dataIndex: number;
        rawIndex: number | null;
        value: number | null;
        timestamp: number | null;
        open: number | null;
        high: number | null;
        low: number | null;
        close: number | null;
    };
    chartOptions: { autoScale: boolean };

    clampPanOffset: () => void;
    enforceScaleBounds: (options?: { preserveRange?: boolean }) => void;
    getCloseValue: (index: number) => number | undefined;
    getMaxOffsetForMetrics: (metrics: SlotMetrics | null | undefined) => number;
    getOhlcForIndex: (index: number, target?: OhlcValues | null) => OhlcValues;
    normalizeClampedFloat: (value: number | string | null | undefined, dataValue: number, min?: number, max?: number) => number;
    resetZoom: (options?: { alignToTail?: boolean }) => void;
    setAutoScale: (enabled: boolean | string | null | undefined) => void;
}

const captureViewState = (chart: ViewStateHost): Record<string, JsonValue | null | undefined> => {
    if (chart.dataLength === 0) return {};
    return {
        zoomLevel: chart.zoom.level,
        targetZoomLevel: chart.zoom.targetLevel,
        panOffset: chart.pan.offset,
        panTargetOffset: chart.pan.targetOffset,
        wasAtTail: chart.pan.isAtTail,
        autoScale: chart.scale.auto,
        scale: !chart.scale.auto && isFin(chart.scale.min) ? { min: chart.scale.min, max: chart.scale.max } : null,
        crosshair: chart.crosshair.visible && isFin(chart.crosshair.timestamp) ? { timestamp: chart.crosshair.timestamp } : null
    };
};

const restoreCrosshair = (chart: ViewStateHost, ts: number): void => {
    Object.assign(chart.crosshair, {
        visible: false,
        dataIndex: -1,
        rawIndex: null,
        value: null,
        timestamp: null,
        open: null,
        high: null,
        low: null,
        close: null
    });
    if (!isFin(ts) || chart.dataLength === 0) return;
    let leftValue = 0;
    let redChannel = chart.dataLength - 1;
    let match = -1;
    while (leftValue <= redChannel) {
        const mid = (leftValue + redChannel) >> 1;
        const currentTime = chart.timestamps[mid] ?? Number.NaN;
        if (currentTime === ts) {
            match = mid;
            break;
        }
        if (currentTime < ts) {
            match = mid;
            leftValue = mid + 1;
        } else redChannel = mid - 1;
    }
    if (match === -1) return;
    const currentTime = chart.timestamps[match] ?? null;
    if (!isFin(currentTime) || !isFin(chart.getCloseValue(match))) return;
    chart.crosshair.visible = true;
    chart.crosshair.dataIndex = chart.crosshair.rawIndex = match;
    chart.crosshair.timestamp = currentTime;
    chart.crosshair.value = chart.getCloseValue(match) ?? null;
    chart.getOhlcForIndex(match, chart.crosshair);
};

const restoreViewState = (chart: ViewStateHost, stringValue: Record<string, JsonValue | null | undefined>): void => {
    if (!Object.keys(stringValue).length) {
        chart.resetZoom();
        return;
    }

    const autoScaleRaw = stringValue['autoScale'] ?? chart.chartOptions.autoScale;
    const autoScaleValue = typeof autoScaleRaw === 'boolean' || typeof autoScaleRaw === 'string' ? autoScaleRaw : chart.chartOptions.autoScale;
    const autoScaleEnabled = Boolean(autoScaleValue);
    if (chart.scale.auto !== autoScaleEnabled) chart.setAutoScale(autoScaleValue);
    else chart.scale.auto = autoScaleEnabled;

    const scaleObject = stringValue['scale'];
    if (!autoScaleEnabled && scaleObject && isPlainObject(scaleObject)) {
        const scMinRaw = scaleObject['min'];
        const scMaxRaw = scaleObject['max'];
        const scMin = readRuntimeFiniteNumberOrFallbackValue(scMinRaw, Number.NaN);
        const scMax = readRuntimeFiniteNumberOrFallbackValue(scMaxRaw, Number.NaN);
        if (isFin(scMin) && isFin(scMax) && scMax > scMin) {
            chart.scale.min = scMin;
            chart.scale.max = scMax;
            chart.enforceScaleBounds({ preserveRange: true });
        }
    }

    const zoomLevelValue = stringValue['zoomLevel'];
    const targetZoomLevelValue = stringValue['targetZoomLevel'];
    const zoomLevelInput = typeof zoomLevelValue === 'number' || typeof zoomLevelValue === 'string' ? zoomLevelValue : null;
    const targetZoomLevelInput = typeof targetZoomLevelValue === 'number' || typeof targetZoomLevelValue === 'string' ? targetZoomLevelValue : null;
    chart.zoom.level = chart.normalizeClampedFloat(zoomLevelInput, 1, chart.zoom.minLevel, chart.zoom.maxLevel);
    chart.zoom.targetLevel = chart.normalizeClampedFloat(targetZoomLevelInput, chart.zoom.level, chart.zoom.minLevel, chart.zoom.maxLevel);
    chart.zoom.isAnimating = false;

    const maxOff = chart.getMaxOffsetForMetrics(null);
    const panOffset = stringValue['wasAtTail'] ? maxOff : readRuntimeFiniteNumberOrFallbackValue(stringValue['panOffset'], maxOff);
    chart.pan.offset = clampNumber(panOffset, 0, maxOff);
    chart.pan.targetOffset = readRuntimeFiniteNumberOrFallbackValue(stringValue['panTargetOffset'], chart.pan.offset);
    chart.pan.startOffset = chart.pan.offset;
    chart.pan.velocity = 0;
    chart.pan.isZooming = false;
    chart.pan.isAtTail = Math.abs(chart.pan.offset - maxOff) < 1e-3;

    const crosshairState = stringValue['crosshair'];
    const crosshairTimestampRaw = isObject(crosshairState) ? crosshairState['timestamp'] : null;
    restoreCrosshair(chart, readRuntimeFiniteNumberOrFallbackValue(crosshairTimestampRaw, Number.NaN));
    chart.clampPanOffset();
};

const validateDataPoint = (point: { timestamp: JsonValue | null | undefined; value?: JsonValue | null | undefined | undefined } & Record<string, JsonValue | null | undefined>): boolean => {
    const timestamp = readRuntimeFiniteNumberOrFallbackValue(point.timestamp, null);
    if (timestamp === null) {
        return false;
    }
    if ('value' in point) {
        const value = readRuntimeFiniteNumberOrFallbackValue(point.value, null);
        if (value !== null) {
            return true;
        }
    }
    if (!('open' in point) || !('high' in point) || !('low' in point) || !('close' in point)) return false;
    return [point['open'], point['high'], point['low'], point['close']].every((value) => readRuntimeFiniteNumberOrFallbackValue(value, null) !== null);
};

export { captureViewState, restoreCrosshair, restoreViewState, validateDataPoint };
