/* SoAI - Chart vertical scale calculation [frontend/assets/ts/features/charts/component/data/verticalScale.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scaleChartAnimationDurationMs } from '@core/animations/chartMotion.ts';
import { monotonicMs } from '@core/time/clock.ts';
import type { ChartOptions } from '@features/charts/chartTypes.ts';
import { DEFAULT_VERTICAL_SCALE_PADDING_RATIO, MIN_VERTICAL_PIXEL_PADDING } from '@features/charts/component/chartComponentStatics.ts';
import type { Scale, VisibleRangeStats } from '@features/charts/component/chartComponentTypes.ts';
import { resolveBoundedScale } from '@features/charts/scales/scaleBounds.ts';
import { glideScaleTowards, SCALE_GLIDE_MS, stopScaleGlide, type ScaleGlideState } from '@features/charts/scales/scaleGlide.ts';

interface VerticalScaleHost {
    chartOptions: ChartOptions;
    visibleRangeStats: VisibleRangeStats;
    scale: Scale;
    scaleGlide: ScaleGlideState;
    yAxisMinRange: number;
    element: HTMLElement;
}

interface VerticalScaleCalculations {
    getChartDimensions: () => { chartHeight: number };
}

interface ScaleRange {
    min: number;
    max: number;
}

const SCALE_CONTRACTION_RATIO = 0.85;

const resolvePaddedRange = (chart: VerticalScaleHost, chartHeight: number, statMin: number, statMax: number): ScaleRange => {
    const ratio = chart.chartOptions.verticalPaddingRatio > 0 ? chart.chartOptions.verticalPaddingRatio : DEFAULT_VERTICAL_SCALE_PADDING_RATIO;
    const pixelPadding = chartHeight > 0 ? MIN_VERTICAL_PIXEL_PADDING : 0;
    if (chart.chartOptions.scaleType === 'logarithmic') {
        const logMin = Math.log10(Math.max(statMin, 1e-9));
        const logMax = Math.log10(Math.max(statMax, 10 ** logMin * 1.01));
        const range = Math.max(logMax - logMin, 1e-6);
        const padding = Math.max(range * ratio, 1e-6, pixelPadding > 0 ? (range / chartHeight) * pixelPadding : 0);
        return { min: 10 ** (logMin - padding), max: 10 ** (logMax + padding) };
    }
    const range = statMax - statMin;
    const magnitude = range > 0 ? range : Math.max(Math.abs(statMin), Math.abs(statMax), 1);
    const padding = Math.max(magnitude * ratio, range > 0 && pixelPadding > 0 ? (range / chartHeight) * pixelPadding : 0);
    return { min: statMin - padding, max: statMax + padding };
};

const toScaleSpace = (value: number, logarithmic: boolean): number => (logarithmic ? Math.log10(value) : value);

const applyHysteresis = (target: ScaleRange, current: ScaleRange | null, logarithmic: boolean): ScaleRange => {
    if (!current) return target;
    const contains = target.min >= current.min && target.max <= current.max;
    const currentSpan = toScaleSpace(current.max, logarithmic) - toScaleSpace(current.min, logarithmic);
    const targetSpan = toScaleSpace(target.max, logarithmic) - toScaleSpace(target.min, logarithmic);
    return contains && currentSpan > 0 && targetSpan >= currentSpan * SCALE_CONTRACTION_RATIO ? current : target;
};

const resolveCurrentTarget = (chart: VerticalScaleHost): ScaleRange | null => {
    const { scale, scaleGlide } = chart;
    if (scale.min === null || scale.max === null) return null;
    return scaleGlide.active ? { min: scaleGlide.toMin, max: scaleGlide.toMax } : { min: scale.min, max: scale.max };
};

const updateScale = (chart: VerticalScaleHost, calculations: VerticalScaleCalculations): void => {
    const { min: statMin, max: statMax, count } = chart.visibleRangeStats;
    if (!chart.scale.auto) {
        stopScaleGlide(chart.scaleGlide);
        return;
    }
    if (count === 0 || statMin === null || statMax === null) {
        if (count === 0) {
            chart.scale.min = null;
            chart.scale.max = null;
            stopScaleGlide(chart.scaleGlide);
        }
        return;
    }
    const chartHeight = Math.max(0, calculations.getChartDimensions().chartHeight || 0);
    const padded = resolvePaddedRange(chart, chartHeight, statMin, statMax);
    const bounded = resolveBoundedScale(chart, padded.min, padded.max, false);
    const target = applyHysteresis(bounded, resolveCurrentTarget(chart), chart.chartOptions.scaleType === 'logarithmic');
    glideScaleTowards(chart.scaleGlide, chart.scale, target.min, target.max, scaleChartAnimationDurationMs(SCALE_GLIDE_MS, chart.element), monotonicMs());
};

export { updateScale };
