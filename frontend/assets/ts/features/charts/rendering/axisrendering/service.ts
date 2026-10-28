/* SoAI - Charts feature axis rendering service [frontend/assets/ts/features/charts/rendering/axisrendering/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatYAxisLabels } from '@features/charts/rendering/axisrendering/valueLabels.ts';
import { isString } from '@core/typeGuards.ts';
import { timeToX } from '@features/charts/viewport/timeViewport.ts';
import { DEFAULT_Y_TICK_COUNT, LOG_SAFE_MIN, MIN_LABEL_GAP, X_AXIS_GAP_RATIO, X_AXIS_PADDING, determineXAxisLabelBudget } from '@features/charts/rendering/axisrendering/constants.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import type { ChartDimensions, RenderGeometry, XAxisTick, YAxisTick } from '@features/charts/rendering/renderingModels.ts';

const { isFinite: isFin } = Number;
const { abs, ceil, floor, log10, max, min, round } = Math;

const niceStep = (rawStep: number): number => {
    if (!isFin(rawStep) || rawStep <= 0) {
        return 1;
    }
    const exponent = floor(log10(rawStep));
    const fraction = rawStep / 10 ** exponent;
    const niceFraction = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 2.5 ? 2.5 : fraction <= 5 ? 5 : 10;
    return niceFraction * 10 ** exponent;
};

const dedupeAndLimitTicks = (values: number[], limit: number): number[] => {
    if (!Array.isArray(values) || values.length === 0) {
        return [];
    }

    const filtered = values
        .filter((value): value is number => isFin(value))
        .map((value) => +value)
        .sort((left, right) => right - left);
    if (!filtered.length) {
        return [];
    }

    const epsilon = 1e-9;
    const first = filtered[0];
    if (first === undefined) {
        return [];
    }
    const deduped = [first];
    for (let index = 1; index < filtered.length; index += 1) {
        const lastValue = deduped[deduped.length - 1];
        const candidate = filtered[index];
        if (lastValue !== undefined && candidate !== undefined && abs(lastValue - candidate) > epsilon) {
            deduped.push(candidate);
        }
    }

    if (deduped.length <= limit) {
        return deduped;
    }

    const step = (deduped.length - 1) / max(1, limit - 1);
    const sampled = new Set<number>();
    for (let index = 0; index < limit; index += 1) {
        const dedupedIndex = min(round(index * step), deduped.length - 1);
        const value = deduped[dedupedIndex];
        if (value !== undefined) {
            sampled.add(value);
        }
    }
    return [...sampled];
};

const buildLinearTickValues = (minValue: number, maxValue: number, targetCount: number): number[] => {
    const range = maxValue - minValue;
    if (!isFin(range) || range === 0) {
        return [maxValue, minValue];
    }
    const step = niceStep(range / max(1, targetCount - 1));
    const niceMin = floor(minValue / step) * step;
    const niceMax = ceil(maxValue / step) * step;
    const ticks: number[] = [];

    for (let value = niceMax; value >= niceMin; value -= step) {
        if (value >= minValue - step && value <= maxValue + step) {
            ticks.push(value);
        }
    }
    if (!ticks.length) {
        ticks.push(maxValue, minValue);
    }
    return dedupeAndLimitTicks(ticks, targetCount + 1);
};

const buildLogTickValues = (minValue: number, maxValue: number, targetCount: number): number[] => {
    const safeMin = max(minValue, LOG_SAFE_MIN);
    const safeMax = max(maxValue, safeMin * 1.0001);
    const logMin = log10(safeMin);
    const logMax = log10(safeMax);
    if (!isFin(logMin) || !isFin(logMax)) {
        return buildLinearTickValues(minValue, maxValue, targetCount);
    }

    const ticks: number[] = [];
    const startExp = floor(logMin);
    for (let exponent = ceil(logMax); exponent >= startExp; exponent -= 1) {
        const base = 10 ** exponent;
        if (base >= safeMin && base <= safeMax) {
            ticks.push(base);
        }
        const mid = base * 2;
        if (mid >= safeMin && mid <= safeMax) {
            ticks.push(mid);
        }
        const upper = base * 5;
        if (upper >= safeMin && upper <= safeMax) {
            ticks.push(upper);
        }
    }
    ticks.push(safeMax, safeMin);
    return dedupeAndLimitTicks(ticks, targetCount + 1);
};

const buildYAxisTickValues = (scene: ChartRenderingScene, targetCount: number = DEFAULT_Y_TICK_COUNT): number[] => {
    const { min: scaleMin, max: scaleMax } = scene.state.scale;
    if (scaleMin === null || scaleMax === null) {
        return [];
    }
    if (!isFin(scaleMin) || !isFin(scaleMax)) {
        return [];
    }
    return scene.state.options['scaleType'] === 'logarithmic' ? buildLogTickValues(scaleMin, scaleMax, targetCount) : buildLinearTickValues(scaleMin, scaleMax, targetCount);
};

const generateYAxisTicks = (scene: ChartRenderingScene, dims: ChartDimensions, viewport: { top: number; height: number }): YAxisTick[] => {
    const values = buildYAxisTickValues(scene, DEFAULT_Y_TICK_COUNT);
    if (!values.length) {
        return [];
    }

    const height = isFin(viewport.height) ? viewport.height : Number(dims['chartHeight']) || 0;
    const top = isFin(viewport.top) ? viewport.top : Number(dims['top']) || 0;
    const result: YAxisTick[] = [];

    const labels = formatYAxisLabels(values, scene.format.formatValue, dims.width);
    for (const [index, value] of values.entries()) {
        if (!isFin(value)) {
            continue;
        }
        const yCoordinate = scene.format.valueToPixel(value, height, top);
        if (isFin(yCoordinate)) {
            result.push({ value, label: labels[index] ?? scene.format.formatValue(value), y: yCoordinate });
        }
    }
    return result;
};

const SECOND_MS = 1000;
const MINUTE_MS = 60 * SECOND_MS;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;
const TIME_TICK_STEPS_MS: readonly number[] = [SECOND_MS, 2 * SECOND_MS, 5 * SECOND_MS, 10 * SECOND_MS, 15 * SECOND_MS, 30 * SECOND_MS, MINUTE_MS, 2 * MINUTE_MS, 5 * MINUTE_MS, 10 * MINUTE_MS, 15 * MINUTE_MS, 30 * MINUTE_MS, HOUR_MS, 2 * HOUR_MS, 3 * HOUR_MS, 6 * HOUR_MS, 12 * HOUR_MS, DAY_MS, 2 * DAY_MS, 7 * DAY_MS, 14 * DAY_MS, 30 * DAY_MS, 90 * DAY_MS, 180 * DAY_MS, 365 * DAY_MS];

const resolveTimeTickStep = (msPerPx: number, minimumSpacingPx: number): number => TIME_TICK_STEPS_MS.find((step) => step / msPerPx >= minimumSpacingPx) ?? TIME_TICK_STEPS_MS[TIME_TICK_STEPS_MS.length - 1] ?? DAY_MS;

const resolveLocalOffsetMs = (timestamp: number, stepMs: number): number => (stepMs >= HOUR_MS ? new Date(timestamp).getTimezoneOffset() * MINUTE_MS : 0);

const alignTimeTick = (timestamp: number, stepMs: number): number => {
    const offsetMs = resolveLocalOffsetMs(timestamp, stepMs);
    return floor((timestamp - offsetMs) / stepMs) * stepMs + offsetMs;
};

const generateXAxisTicks = (scene: ChartRenderingScene, context: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D, dims: ChartDimensions, geometry: RenderGeometry): XAxisTick[] => {
    const ticks: XAxisTick[] = [];
    const maxLabels = determineXAxisLabelBudget(geometry.plotWidth);
    if (maxLabels <= 0 || scene.state.dataLength === 0) {
        return ticks;
    }
    const stepMs = resolveTimeTickStep(geometry.msPerPx, geometry.plotWidth / maxLabels);
    const minimalGap = max(MIN_LABEL_GAP, 12 * X_AXIS_GAP_RATIO);
    const rightLimit = dims.left + geometry.plotWidth;
    let lastLabelRight = -Infinity;
    for (let timestamp = alignTimeTick(geometry.startTs, stepMs); timestamp <= geometry.endTs; timestamp = alignTimeTick(timestamp + stepMs * 1.5, stepMs)) {
        const xCoordinate = timeToX(geometry, timestamp);
        const label = scene.format.formatAxisTimestamp?.(timestamp, geometry.span) ?? scene.format.formatTimestamp(timestamp);
        if (!label || !isString(label)) continue;
        const halfWidth = context.measureText(label).width / 2;
        if (xCoordinate - halfWidth < dims.left + X_AXIS_PADDING || xCoordinate + halfWidth > rightLimit - X_AXIS_PADDING || xCoordinate - halfWidth <= lastLabelRight + minimalGap) continue;
        ticks.push({ x: xCoordinate, timestamp, label, textWidth: halfWidth * 2 });
        lastLabelRight = xCoordinate + halfWidth;
    }
    return ticks;
};

export { generateYAxisTicks, generateXAxisTicks };
