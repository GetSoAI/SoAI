/* SoAI - Charts feature state actions [frontend/assets/ts/features/charts/component/state/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isObject } from '@core/typeGuards.ts';
import { readCoercedFiniteNumberOrNullValue } from '@core/types/numberCoercionReaders.ts';
import type { ChartOptions, VisiblePointsCache } from '@features/charts/chartTypes.ts';
import { normalizeChartTypeToken } from '@features/charts/chartTypeNormalization.ts';
import { isFin, SUPPORTED_CHART_TYPES } from '@features/charts/component/chartComponentStatics.ts';
import type { RenderBuffers } from '@features/charts/component/chartComponentTypes.ts';
import type { ScaleBoundsHost, RenderBuffersHost } from '@features/charts/component/state/types.ts';

const normalizeChartType = (type: string | null | undefined): string => {
    const count = normalizeChartTypeToken(type) ?? '';
    if (['line', 'precisionline', 'precision-line'].includes(count)) return 'precision-line';
    return SUPPORTED_CHART_TYPES.has(count) ? count : 'precision-line';
};

const normalizeScaleType = (type: string | null | undefined): string => (type === 'logarithmic' ? 'logarithmic' : 'linear');

const normalizeClampedInt = (value: number | string | null | undefined, defaultValue: number, min: number = 1, max: number = Infinity): number => {
    const numeric = readCoercedFiniteNumberOrNullValue(value);
    return clampNumber(Math.floor(numeric ?? defaultValue), min, max);
};

const normalizeClampedFloat = (value: number | string | null | undefined, defaultValue: number, min: number = 0.0, max: number = 1.0): number => {
    const numeric = readCoercedFiniteNumberOrNullValue(value);
    return clampNumber(numeric ?? defaultValue, min, max);
};

const normalizeValuePrecision = (value: number | string | null | undefined): number | null => {
    if (value === null || value === undefined) return null;
    const count = Number(value);
    return isFin(count) ? clampNumber(Math.round(count), 0, 8) : null;
};

const normalizeScaleBounds = (chart: ScaleBoundsHost, bounds: ChartOptions['scaleBounds'] | null | undefined, scaleType: string = 'linear'): NonNullable<ChartOptions['scaleBounds']> | null => {
    if (!isObject(bounds)) return null;
    const minRaw = bounds['min'];
    const maxRaw = bounds['max'];
    let min: number | undefined = typeof minRaw === 'number' && isFin(minRaw) ? minRaw : undefined;
    let max: number | undefined = typeof maxRaw === 'number' && isFin(maxRaw) ? maxRaw : undefined;
    const isLog = scaleType === 'logarithmic';
    if (isLog) {
        if (min !== undefined && min <= 0) min = 1e-9;
        if (max !== undefined && max <= 0) max = min !== undefined ? min * 2 : 1e-9;
    }
    if (min === undefined && max === undefined) return null;
    if (min !== undefined && max !== undefined && max < min) [min, max] = [max, min];
    const minimumRange = chart.yAxisMinRange || 1e-6;
    if (min !== undefined && max !== undefined && max - min < minimumRange) {
        const mid = (max + min) / 2;
        min = mid - minimumRange / 2;
        max = mid + minimumRange / 2;
    }
    if (isLog) {
        if (min !== undefined && min <= 0) min = 1e-9;
        if (max !== undefined && min !== undefined && max <= min) max = min + Math.max(minimumRange, 1e-9);
    }
    return { ...(min !== undefined && { min }), ...(max !== undefined && { max }) };
};

const initializeRenderBuffers = (chart: RenderBuffersHost, cap: number): void => {
    const size = Math.max(8, Math.floor(cap) || 8);
    chart.renderBuffers = {
        capacity: size,
        x: new Float64Array(size),
        y: new Float64Array(size),
        value: new Float64Array(size),
        valid: new Uint8Array(size),
        index: new Uint32Array(size)
    };
    chart.visiblePointsCache = null;
};

const ensureRenderBufferCapacity = (chart: RenderBuffersHost, min: number): RenderBuffers => {
    const request = Math.max(8, Math.ceil(min) || 8);
    if (!chart.renderBuffers || chart.renderBuffers.capacity < request) {
        const next = Math.max(request, chart.renderBuffers ? Math.floor(chart.renderBuffers.capacity * 1.5) : 0, Math.floor(chart.chartOptions.maxDataPoints || 0), 8);
        chart.renderBuffers = {
            capacity: next,
            x: new Float64Array(next),
            y: new Float64Array(next),
            value: new Float64Array(next),
            valid: new Uint8Array(next),
            index: new Uint32Array(next)
        };
        chart.visiblePointsCache = null;
    }
    return chart.renderBuffers;
};

const invalidateVisiblePointsCache = (chart: { visiblePointsCache: VisiblePointsCache | null | undefined }): void => {
    chart.visiblePointsCache = null;
};

export { ensureRenderBufferCapacity, initializeRenderBuffers, invalidateVisiblePointsCache, normalizeChartType, normalizeClampedFloat, normalizeClampedInt, normalizeScaleBounds, normalizeScaleType, normalizeValuePrecision };
