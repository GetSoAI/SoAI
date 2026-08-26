/* SoAI - Charts feature axis rendering service [frontend/assets/ts/features/charts/rendering/axisrendering/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { getXForVisibleIndex } from '@features/charts/layout/geometry.ts';
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

    for (const value of values) {
        if (!isFin(value)) {
            continue;
        }
        const yCoordinate = scene.format.valueToPixel(value, height, top);
        if (isFin(yCoordinate)) {
            result.push({ value, label: scene.format.formatValue(value), y: yCoordinate });
        }
    }
    return result;
};

const generateXAxisTicks = (scene: ChartRenderingScene, context: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D, dims: ChartDimensions, geometry: RenderGeometry): XAxisTick[] => {
    const ticks: XAxisTick[] = [];
    const { displayCount: displayCountValue, start, offsetFraction } = scene.state.visibleRange;
    const displayCount = Number(displayCountValue) || 0;
    if (displayCount <= 0 || scene.state.dataLength === 0) {
        return ticks;
    }

    const availableWidth = isFin(geometry['effectiveWidth']) ? geometry['effectiveWidth'] : Number(dims['chartWidth']) || 0;
    const maxLabels = determineXAxisLabelBudget(availableWidth);
    if (maxLabels <= 0) {
        return ticks;
    }

    const spanMs = scene.geometry.getVisibleTimeSpan?.() ?? 0;
    const spacing = geometry['spacing'] || availableWidth / max(1, displayCount - 1);
    const originX = (geometry['originX'] ?? geometry['baseLeft'] ?? dims['left']) - spacing * offsetFraction;
    const effectiveVisible = max(1, geometry['visibleCount'] ?? min(displayCount, scene.state.dataLength - start));
    const endIndex = min(scene.state.dataLength - 1, start + effectiveVisible - 1);
    if (endIndex < start) {
        return ticks;
    }

    const candidateIndices: number[] = [start];
    const baseStep = max(1, round(effectiveVisible / max(1, maxLabels - 1)));
    for (let index = start + baseStep; index < endIndex; index += baseStep) {
        candidateIndices.push(index);
    }
    if (candidateIndices[candidateIndices.length - 1] !== endIndex) {
        candidateIndices.push(endIndex);
    }

    let lastLabelRight = -Infinity;
    const rightLimit = geometry['rightBoundary'] ?? (Number(dims['left']) || 0) + availableWidth;
    const minimalGap = max(MIN_LABEL_GAP, 12 * X_AXIS_GAP_RATIO);
    const timestamps = scene.state.timestamps;

    for (const index of candidateIndices) {
        const xCoordinate = getXForVisibleIndex(scene.state, index - start, displayCount, originX, spacing, geometry, dims);
        const timestamp = timestamps[index];
        if (timestamp === undefined || !isFin(timestamp)) {
            continue;
        }

        const labelResult = scene.format.formatAxisTimestamp?.(timestamp, spanMs) ?? scene.format.formatTimestamp(timestamp);
        if (!labelResult || !isString(labelResult)) {
            continue;
        }

        const halfWidth = context.measureText(labelResult).width / 2;
        const minX = (Number(dims['left']) || 0) + halfWidth + X_AXIS_PADDING;
        const clampedX = max(minX, min(xCoordinate, max(minX, rightLimit - halfWidth - X_AXIS_PADDING)));

        if (clampedX - halfWidth <= lastLabelRight + minimalGap) {
            continue;
        }

        ticks.push({ x: clampedX, timestamp, label: labelResult, textWidth: halfWidth * 2 });
        lastLabelRight = clampedX + halfWidth;
        if (ticks.length >= maxLabels) {
            break;
        }
    }

    const endTimestamp = timestamps[endIndex];
    if (!ticks.length && endTimestamp !== undefined && isFin(endTimestamp)) {
        const labelResult = scene.format.formatAxisTimestamp?.(endTimestamp, spanMs) ?? scene.format.formatTimestamp(endTimestamp);
        if (labelResult && isString(labelResult)) {
            ticks.push({
                x: geometry['rightBoundary'] ?? (Number(dims['left']) || 0) + availableWidth,
                timestamp: endTimestamp,
                label: labelResult,
                textWidth: context.measureText(labelResult).width
            });
        }
    }

    return ticks;
};

export { generateYAxisTicks, generateXAxisTicks };
