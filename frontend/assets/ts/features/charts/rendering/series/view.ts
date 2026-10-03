/* SoAI - Charts feature series rendering [frontend/assets/ts/features/charts/rendering/series/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartDimensions, RenderGeometry, ValueViewport } from '@features/charts/rendering/renderingModels.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import { getValueViewport } from '@features/charts/rendering/axes.ts';
import type { VisiblePointsWithBuffers } from '@features/charts/renderingTypes.ts';
import { hexToRgba } from '@features/charts/rendering/primitives.ts';
import { drawEndpointMarker, strokeSplineSegment } from '@features/charts/rendering/series/effects.ts';
import { findLatestValidIndex } from '@features/charts/rendering/series/state.ts';
import { isMissingSampleInterval } from '@features/charts/rendering/series/sampleGaps.ts';
import { resolveVisibleColumnWidth } from '@features/charts/rendering/series/columnWidth.ts';
import { plotRight } from '@features/charts/viewport/timeViewport.ts';

const { min, max, abs } = Math;
const { isFinite: isFiniteNumber } = Number;

interface GapRendering {
    timestamps: Float64Array;
    intervalMs: number;
}

const isGap = (points: VisiblePointsWithBuffers, previous: number, current: number, gap: GapRendering | null): boolean => {
    if (!gap || gap.intervalMs <= 0) return false;
    const previousIndex = points.index[previous];
    const currentIndex = points.index[current];
    if (previousIndex === undefined || currentIndex === undefined) return false;
    const previousTimestamp = gap.timestamps[previousIndex];
    const currentTimestamp = gap.timestamps[currentIndex];
    return previousTimestamp !== undefined && currentTimestamp !== undefined && isMissingSampleInterval(previousTimestamp, currentTimestamp, gap.intervalMs);
};

const drawGapConnector = (context: CanvasRenderingContext2D, points: VisiblePointsWithBuffers, previous: number, current: number): void => {
    const startX = points.x[previous];
    const startY = points.y[previous];
    const endX = points.x[current];
    const endY = points.y[current];
    if (startX === undefined || startY === undefined || endX === undefined || endY === undefined) return;
    context.save();
    context.setLineDash([3, 5]);
    context.beginPath();
    context.moveTo(startX, startY);
    context.lineTo(endX, endY);
    context.stroke();
    context.restore();
};

const drawLine = (context: CanvasRenderingContext2D, points: VisiblePointsWithBuffers, color: string, gap: GapRendering | null = null): void => {
    const { x: xCoordinate, y: yCoordinate, valid, length: len } = points;
    if (!len) return;
    context.strokeStyle = color;
    context.lineWidth = 2;
    let previous = -1;
    for (let index = 0; index < len; index++) {
        const validValue = valid[index];
        if (validValue !== undefined && validValue) {
            const xValue = xCoordinate[index];
            const yValue = yCoordinate[index];
            if (xValue !== undefined && yValue !== undefined) {
                if (previous >= 0) {
                    if (isGap(points, previous, index, gap)) drawGapConnector(context, points, previous, index);
                    else {
                        context.beginPath();
                        const previousX = xCoordinate[previous];
                        const previousY = yCoordinate[previous];
                        if (previousX === undefined || previousY === undefined) continue;
                        context.moveTo(previousX, previousY);
                        context.lineTo(xValue, yValue);
                        context.stroke();
                    }
                } else if (index + 1 >= len || !valid[index + 1]) {
                    context.beginPath();
                    context.arc(xValue, yValue, 2, 0, Math.PI * 2);
                    context.fillStyle = color;
                    context.fill();
                }
                previous = index;
            }
        } else previous = -1;
    }
};

const drawSpline = (context: CanvasRenderingContext2D, points: VisiblePointsWithBuffers, color: string, gap: GapRendering | null = null): void => {
    const { length: len } = points;
    if (!len) return;
    context.strokeStyle = color;
    context.lineWidth = 2;
    const tension = 0.5;
    let segStart = -1;
    for (let index = 0; index < len; index++) {
        const validValue = points.valid[index];
        if (validValue !== undefined && validValue) {
            if (segStart === -1) segStart = index;
            else if (isGap(points, index - 1, index, gap)) {
                strokeSplineSegment(context, points, segStart, index - 1, tension);
                drawGapConnector(context, points, index - 1, index);
                segStart = index;
            }
        } else if (segStart !== -1) {
            strokeSplineSegment(context, points, segStart, index - 1, tension);
            segStart = -1;
        }
    }
    if (segStart !== -1) strokeSplineSegment(context, points, segStart, len - 1, tension);
};

const createAreaFill = (context: CanvasRenderingContext2D, valueViewport: ValueViewport, color: string): CanvasGradient => {
    const gradient = context.createLinearGradient(0, valueViewport.top, 0, valueViewport.bottom);
    gradient.addColorStop(0, hexToRgba(color, 0.5));
    gradient.addColorStop(1, hexToRgba(color, 0));
    return gradient;
};

const drawArea = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, points: VisiblePointsWithBuffers, dims: ChartDimensions, color: string): void => {
    const { x: xCoordinate, y: yCoordinate, valid, length: len } = points;
    if (!len) return;
    const valueViewport = getValueViewport(scene, dims);
    const baseline = valueViewport.bottom;
    context.fillStyle = createAreaFill(context, valueViewport, color);

    let segStart = -1;
    let lastValidX = 0;
    const gap = { timestamps: scene.state.timestamps, intervalMs: scene.state.chartOptions.expectedSampleIntervalMs };
    for (let index = 0; index < len; index++) {
        const validValue = valid[index];
        if (validValue !== undefined && validValue) {
            const xValue = xCoordinate[index];
            const yValue = yCoordinate[index];
            if (xValue !== undefined && yValue !== undefined) {
                if (segStart !== -1 && isGap(points, index - 1, index, gap)) {
                    context.lineTo(lastValidX, baseline);
                    context.fill();
                    segStart = -1;
                }
                if (segStart === -1) {
                    segStart = index;
                    context.beginPath();
                    context.moveTo(xValue, baseline);
                }
                context.lineTo(xValue, yValue);
                lastValidX = xValue;
            }
        } else if (segStart !== -1) {
            context.lineTo(lastValidX, baseline);
            context.fill();
            segStart = -1;
        }
    }
    if (segStart !== -1) {
        context.lineTo(lastValidX, baseline);
        context.fill();
    }

    drawLine(context, points, color, gap);
    if (scene.state.chartOptions.chartType === 'area') {
        const index = findLatestValidIndex(points);
        if (index !== -1) {
            const xValue = points.x[index];
            const yValue = points.y[index];
            const markerColor = scene.state.chartOptions.colors.textSecondary || scene.state.chartOptions.colors.grid || scene.state.chartOptions.colors.text || '#8a8f98';
            if (xValue !== undefined && yValue !== undefined) drawEndpointMarker(context, xValue, yValue, markerColor);
        }
    }
};

const drawBars = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, points: VisiblePointsWithBuffers, baseline: number, color: string, geometry: RenderGeometry): void => {
    const { x: xCoordinate, y: yCoordinate, valid, length: len } = points;
    if (!len) return;
    const leftBound = geometry.plotLeft;
    const rightBound = plotRight(geometry);
    context.fillStyle = color;
    for (let index = 0; index < len; index++) {
        const validValue = valid[index];
        if (validValue === undefined || !validValue) continue;
        const xValue = xCoordinate[index];
        const yValue = yCoordinate[index];
        if (xValue === undefined || yValue === undefined) continue;
        const barWidth = resolveVisibleColumnWidth(geometry, points, index, 22, 0.65);
        const halfBar = barWidth / 2;
        if (xValue < leftBound - halfBar || xValue > rightBound + halfBar) continue;
        context.fillRect(xValue - halfBar, min(yValue, baseline), barWidth, max(1, abs(baseline - yValue)));
    }
    context.save();
    context.strokeStyle = color;
    context.lineWidth = 1.5;
    const gap = { timestamps: scene.state.timestamps, intervalMs: scene.state.chartOptions.expectedSampleIntervalMs };
    for (let index = 1; index < len; index++) {
        if (valid[index - 1] && valid[index] && isGap(points, index - 1, index, gap)) drawGapConnector(context, points, index - 1, index);
    }
    context.restore();
};

const drawDeviation = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, points: VisiblePointsWithBuffers, dims: ChartDimensions, geometry: RenderGeometry): void => {
    if (!points.length) return;
    const baselineValue = scene.state.legendData['baseline'];
    const baseline = typeof baselineValue === 'number' && isFiniteNumber(baselineValue) ? baselineValue : null;
    const colors = scene.state.chartOptions.colors;
    const themeStyles = scene.geometry.getThemeStyles();
    const guideColor = themeStyles?.axisGuideColor || colors.grid || colors.textSecondary || colors.text || colors.background || '';
    const fallbackColor = themeStyles?.legendTextColor || colors.primary || colors.secondary || colors.tertiary || colors.quaternary || colors.statusGreen || colors.text || colors.textSecondary || colors.background || '';
    if (baseline === null || !isFiniteNumber(baseline)) {
        const fallbackPrimary = fallbackColor;
        drawArea(scene, context, points, dims, fallbackPrimary);
        return;
    }

    const valueViewport = getValueViewport(scene, dims);
    const baseY = scene.format.valueToPixel(baseline, valueViewport.height, valueViewport.top);
    const leftBound = geometry.plotLeft;
    const rightBound = plotRight(geometry);

    context.save();
    context.lineWidth = 1;
    context.strokeStyle = hexToRgba(guideColor, 0.35);
    context.setLineDash([4, 3]);
    context.beginPath();
    context.moveTo(leftBound, baseY);
    context.lineTo(rightBound, baseY);
    context.stroke();
    context.setLineDash([]);

    const posColor = colors.statusGreen || colors.primary || fallbackColor;
    const negColor = colors.statusRed || fallbackColor;
    const posFill = hexToRgba(posColor, 0.6);
    const posStroke = hexToRgba(posColor, 0.9);
    const negFill = hexToRgba(negColor, 0.6);
    const negStroke = hexToRgba(negColor, 0.9);
    const { x: xCoordinate, y: yCoordinate, valid, value } = points;
    for (let index = 0; index < points.length; index++) {
        const validValue = valid[index];
        if (validValue === undefined || !validValue) continue;
        const valueAt = value[index];
        const xValue = xCoordinate[index];
        const yValue = yCoordinate[index];
        if (valueAt === undefined || xValue === undefined || yValue === undefined) continue;
        const barWidth = resolveVisibleColumnWidth(geometry, points, index, 22, 0.6);
        const halfBar = barWidth / 2;
        const isPos = valueAt >= baseline;
        if (xValue < leftBound - halfBar || xValue > rightBound + halfBar) continue;
        const barX = xValue - halfBar;
        const topY = min(yValue, baseY);
        const height = max(1, abs(yValue - baseY));
        context.fillStyle = isPos ? posFill : negFill;
        context.strokeStyle = isPos ? posStroke : negStroke;
        context.fillRect(barX, topY, barWidth, height);
        context.strokeRect(barX, topY, barWidth, height);
    }
    context.restore();
    drawLine(context, points, hexToRgba(fallbackColor, 0.9), { timestamps: scene.state.timestamps, intervalMs: scene.state.chartOptions.expectedSampleIntervalMs });
};

export { createAreaFill, drawArea, drawBars, drawDeviation, drawLine, drawSpline };
