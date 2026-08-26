/* SoAI - Charts feature series rendering [frontend/assets/ts/features/charts/rendering/series/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartDimensions, RenderGeometry } from '@features/charts/rendering/renderingModels.ts';
import { getRenderGeometry } from '@features/charts/layout/geometry.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import { getValueViewport } from '@features/charts/rendering/axes.ts';
import type { VisiblePointsWithBuffers } from '@features/charts/renderingTypes.ts';
import { hexToRgba } from '@features/charts/rendering/primitives.ts';
import { drawEndpointMarker, strokeSplineSegment } from '@features/charts/rendering/series/effects.ts';
import { findLatestValidIndex } from '@features/charts/rendering/series/state.ts';

const { min, max, abs } = Math;
const { isFinite: isFiniteNumber } = Number;

const drawLine = (context: CanvasRenderingContext2D, points: VisiblePointsWithBuffers, color: string): void => {
    const { x: xCoordinate, y: yCoordinate, valid, length: len } = points;
    if (!len) return;
    context.strokeStyle = color;
    context.lineWidth = 2;
    context.beginPath();
    let pathStarted = false;
    for (let index = 0; index < len; index++) {
        const validValue = valid[index];
        if (validValue !== undefined && validValue) {
            const xValue = xCoordinate[index];
            const yValue = yCoordinate[index];
            if (xValue !== undefined && yValue !== undefined) {
                if (pathStarted) context.lineTo(xValue, yValue);
                else {
                    context.moveTo(xValue, yValue);
                    pathStarted = true;
                }
            }
        } else pathStarted = false;
    }
    context.stroke();
};

const drawSpline = (context: CanvasRenderingContext2D, points: VisiblePointsWithBuffers, color: string): void => {
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
        } else if (segStart !== -1) {
            strokeSplineSegment(context, points, segStart, index - 1, tension);
            segStart = -1;
        }
    }
    if (segStart !== -1) strokeSplineSegment(context, points, segStart, len - 1, tension);
};

const drawArea = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, points: VisiblePointsWithBuffers, dims: ChartDimensions, color: string): void => {
    const { x: xCoordinate, y: yCoordinate, valid, length: len } = points;
    if (!len) return;
    const valueViewport = getValueViewport(scene, dims);
    const baseline = valueViewport.bottom;
    const gradient = context.createLinearGradient(0, valueViewport.top, 0, baseline);
    gradient.addColorStop(0, hexToRgba(color, 0.5));
    gradient.addColorStop(1, hexToRgba(color, 0));
    context.fillStyle = gradient;

    let segStart = -1;
    let lastValidX = 0;
    for (let index = 0; index < len; index++) {
        const validValue = valid[index];
        if (validValue !== undefined && validValue) {
            const xValue = xCoordinate[index];
            const yValue = yCoordinate[index];
            if (xValue !== undefined && yValue !== undefined) {
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

    drawLine(context, points, color);
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

const drawBars = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, points: VisiblePointsWithBuffers, baseline: number, color: string, geometry?: RenderGeometry): void => {
    const { x: xCoordinate, y: yCoordinate, valid, length: len } = points;
    if (!len) return;
    const actualGeometry = geometry || getRenderGeometry(scene.state, scene.geometry, scene.geometry.getChartDimensions());
    const { chartWidth: chartWidthValue, left } = scene.geometry.getChartDimensions();
    const chartWidth = Number(chartWidthValue) || 0;
    const availableWidth = actualGeometry['effectiveWidth'] ?? chartWidth;
    const spacing = actualGeometry['spacing'] ?? 0;
    const pixelsPerBar = scene.geometry.getPixelsPerBar() ?? spacing;
    const innerBarWidth = min(22, availableWidth / max(8, len || 1));
    const widthFromSpacing = min(spacing * 0.65, pixelsPerBar, max(6, innerBarWidth));
    const barWidth = max(2, widthFromSpacing);
    const leftBound = actualGeometry['baseLeft'] ?? left;
    const configuredRightBoundary = actualGeometry['rightBoundary'];
    const rightBoundary = isFiniteNumber(configuredRightBoundary) ? configuredRightBoundary : leftBound + chartWidth;
    const rightBound = max(leftBound, Number(rightBoundary));
    const halfBar = barWidth / 2;

    context.fillStyle = color;
    for (let index = 0; index < len; index++) {
        const validValue = valid[index];
        if (validValue === undefined || !validValue) continue;
        const xValue = xCoordinate[index];
        const yValue = yCoordinate[index];
        if (xValue === undefined || yValue === undefined) continue;
        if (xValue < leftBound - halfBar || xValue > rightBound + halfBar) continue;
        const drawX = max(leftBound, min(xValue - halfBar, rightBound - barWidth));
        context.fillRect(drawX, min(yValue, baseline), barWidth, max(1, abs(baseline - yValue)));
    }
};

const drawDeviation = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, points: VisiblePointsWithBuffers, dims: ChartDimensions, geometry?: RenderGeometry): void => {
    if (!points.length) return;
    const actualGeometry = geometry || getRenderGeometry(scene.state, scene.geometry, dims);
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
    const spacing = actualGeometry['spacing'] ?? 0;
    const pixelsPerBar = scene.geometry.getPixelsPerBar() ?? spacing;
    const barWidth = max(1, pixelsPerBar * 0.6);
    const leftBound = actualGeometry['baseLeft'] ?? dims.left;
    const rightBound = leftBound + (actualGeometry['effectiveWidth'] ?? dims.chartWidth);

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
    const halfBar = barWidth / 2;

    const { x: xCoordinate, y: yCoordinate, valid, value } = points;
    for (let index = 0; index < points.length; index++) {
        const validValue = valid[index];
        if (validValue === undefined || !validValue) continue;
        const valueAt = value[index];
        const xValue = xCoordinate[index];
        const yValue = yCoordinate[index];
        if (valueAt === undefined || xValue === undefined || yValue === undefined) continue;
        const isPos = valueAt >= baseline;
        if (xValue < leftBound - halfBar || xValue > rightBound + halfBar) continue;
        const barX = max(leftBound, min(xValue - halfBar, rightBound - barWidth));
        const topY = min(yValue, baseY);
        const height = max(1, abs(yValue - baseY));
        context.fillStyle = isPos ? posFill : negFill;
        context.strokeStyle = isPos ? posStroke : negStroke;
        context.fillRect(barX, topY, barWidth, height);
        context.strokeRect(barX, topY, barWidth, height);
    }
    context.restore();
    drawLine(context, points, hexToRgba(fallbackColor, 0.9));
};

export { drawArea, drawBars, drawDeviation, drawLine, drawSpline };
