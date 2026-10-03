/* SoAI - Charts feature series service [frontend/assets/ts/features/charts/rendering/series/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { Dataset } from '@features/charts/chartTypes.ts';
import { isOhlcChartType } from '@features/charts/chartTypeNormalization.ts';
import type { OhlcData } from '@features/charts/component/chartComponentTypes.ts';
import { resolveRenderIndexRange } from '@features/charts/component/data/visibleRange.ts';
import { getValueViewport } from '@features/charts/rendering/axes.ts';
import { clipToPlotArea } from '@features/charts/rendering/frame.ts';
import { hexToRgba } from '@features/charts/rendering/primitives.ts';
import type { ChartDimensions, RenderGeometry } from '@features/charts/rendering/renderingModels.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import { hasVisiblePointBuffers, isPlottedOhlc } from '@features/charts/rendering/series/guards.ts';
import { drawEndpointMarker } from '@features/charts/rendering/series/effects.ts';
import { calculateVisiblePoints, findLatestValidIndex } from '@features/charts/rendering/series/state.ts';
import { isMissingSampleInterval } from '@features/charts/rendering/series/sampleGaps.ts';
import { drawArea, drawBars, drawDeviation, drawLine, drawSpline } from '@features/charts/rendering/series/view.ts';
import { timeToX } from '@features/charts/viewport/timeViewport.ts';

const { min, max } = Math;

interface CandlestickPalette {
    up: string;
    down: string;
}

const resolveCandlestickPalette = (scene: ChartRenderingScene): CandlestickPalette => {
    const themeStyles = scene.geometry.getThemeStyles();
    const up = themeStyles.candlestickUpColor;
    const down = themeStyles.candlestickDownColor;
    const upColor = isString(up) ? up.trim() : '';
    const downColor = isString(down) ? down.trim() : '';
    if (!upColor || !downColor) {
        throw new Error('Candlestick rendering requires chart candlestick CSS palette tokens');
    }
    return { up: upColor, down: downColor };
};

const resolvePrimarySeriesColor = (scene: ChartRenderingScene): string => {
    const colors = scene.state.chartOptions.colors;
    const dynamicPrimary = scene.buffers.resolveDynamicPrimaryColor?.();
    return dynamicPrimary && isString(dynamicPrimary) ? dynamicPrimary : colors.secondary || colors.primary || colors.tertiary || colors.quaternary || colors.textSecondary || colors.text || '';
};

const drawCandlestickGapConnectors = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, dims: ChartDimensions, geometry: RenderGeometry, ohlc: OhlcData): void => {
    const intervalMs = scene.state.chartOptions.expectedSampleIntervalMs;
    if (intervalMs <= 0) return;
    const { from, to } = resolveRenderIndexRange(scene.state.visibleRange, scene.state.dataLength);
    if (to - from < 2) return;
    const viewport = getValueViewport(scene, dims);
    const color = scene.state.chartOptions.colors.textSecondary || scene.state.chartOptions.colors.grid || scene.state.chartOptions.colors.text || '';
    const logarithmic = scene.state.chartOptions.scaleType === 'logarithmic';
    context.save();
    context.strokeStyle = hexToRgba(color, 0.8);
    context.lineWidth = scene.geometry.getCssPixelSize?.(1.5) ?? 1.5;
    context.setLineDash([3, 5]);
    for (let currentIndex = from + 1; currentIndex < to; currentIndex++) {
        const previousIndex = currentIndex - 1;
        const previousTimestamp = scene.state.timestamps[previousIndex];
        const currentTimestamp = scene.state.timestamps[currentIndex];
        const previousClose = ohlc.close[previousIndex];
        const currentOpen = ohlc.open[currentIndex];
        if (previousTimestamp === undefined || currentTimestamp === undefined || previousClose === undefined || currentOpen === undefined) continue;
        if (!isMissingSampleInterval(previousTimestamp, currentTimestamp, intervalMs) || !isPlottedOhlc(ohlc.open[previousIndex], ohlc.high[previousIndex], ohlc.low[previousIndex], previousClose, logarithmic) || !isPlottedOhlc(currentOpen, ohlc.high[currentIndex], ohlc.low[currentIndex], ohlc.close[currentIndex], logarithmic)) continue;
        context.beginPath();
        context.moveTo(timeToX(geometry, previousTimestamp), scene.format.valueToPixel(previousClose, viewport.height, viewport.top));
        context.lineTo(timeToX(geometry, currentTimestamp), scene.format.valueToPixel(currentOpen, viewport.height, viewport.top));
        context.stroke();
    }
    context.restore();
};

const drawCandlesticks = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, dims: ChartDimensions, geometry: RenderGeometry, ohlc?: OhlcData | null): void => {
    const valueViewport = getValueViewport(scene, dims);
    const { height, top } = valueViewport;
    const { from, to } = resolveRenderIndexRange(scene.state.visibleRange, scene.state.dataLength);
    if (to <= from || !ohlc) return;

    const bodyWidth = max(scene.geometry.getCssPixelSize?.(1.4) ?? 1.4, min(32, geometry.slotWidth * 0.7));
    const halfWidth = bodyWidth / 2;
    const { open: op, high: hi, low: lo, close: cl } = ohlc;
    const isLog = scene.state.chartOptions.scaleType === 'logarithmic';
    const css1 = scene.geometry.getCssPixelSize?.(1) ?? 1;
    const css11 = max(scene.geometry.getCssPixelSize?.(1.1) ?? 1.1, bodyWidth * 0.12);
    const candlestickPalette = resolveCandlestickPalette(scene);

    context.save();
    context.lineCap = 'butt';
    drawCandlestickGapConnectors(scene, context, dims, geometry, ohlc);

    for (let dataIndex = from; dataIndex < to; dataIndex++) {
        const timestamp = scene.state.timestamps[dataIndex];
        const open = op[dataIndex];
        const high = hi[dataIndex];
        const low = lo[dataIndex];
        const close = cl[dataIndex];
        if (timestamp === undefined || open === undefined || high === undefined || low === undefined || close === undefined) continue;
        if (!isPlottedOhlc(open, high, low, close, isLog)) continue;
        const color = close >= open ? candlestickPalette.up : candlestickPalette.down;
        const xCoordinate = timeToX(geometry, timestamp);
        const highY = scene.format.valueToPixel(high, height, top);
        const lowY = scene.format.valueToPixel(low, height, top);
        const openY = scene.format.valueToPixel(open, height, top);
        const closeY = scene.format.valueToPixel(close, height, top);

        context.strokeStyle = color;
        context.lineWidth = css1;
        context.beginPath();
        context.moveTo(xCoordinate, highY);
        context.lineTo(xCoordinate, lowY);
        context.stroke();

        context.fillStyle = color;
        context.lineWidth = css11;
        const bodyTop = min(openY, closeY);
        const bodyHeight = max(css1, Math.abs(closeY - openY));
        context.fillRect(xCoordinate - halfWidth, bodyTop, bodyWidth, bodyHeight);
        context.strokeRect(xCoordinate - halfWidth, bodyTop, bodyWidth, bodyHeight);
    }
    context.restore();
};

const drawMultiLineData = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, dims: ChartDimensions, geometry: RenderGeometry): void => {
    const colors = scene.state.chartOptions.colors;
    const { secondary, tertiary, quaternary } = colors;
    const defaultPalette = [secondary, tertiary, quaternary].filter((color): color is string => Boolean(color));
    const defaultLineColor = secondary || colors.primary || '';

    scene.state.datasets.forEach((ds: Dataset, index: number) => {
        const vals = ds?.values;
        if (!vals?.length) return;
        const pts = calculateVisiblePoints(scene, vals, vals.length, dims, geometry);
        if (!pts.length) return;
        if (!hasVisiblePointBuffers(pts)) return;
        const defaultColor = defaultPalette.length > 0 ? defaultPalette[index % defaultPalette.length] : undefined;
        const col = (isString(ds.color) ? ds.color : null) || defaultColor || secondary || defaultLineColor;
        drawLine(context, pts, col, { timestamps: scene.state.timestamps, intervalMs: scene.state.chartOptions.expectedSampleIntervalMs });
        if (ds.showEndpointMarker !== false) {
            const index = findLatestValidIndex(pts);
            if (index !== -1) {
                const xValue = pts.x[index];
                const yValue = pts.y[index];
                if (typeof xValue === 'number' && typeof yValue === 'number') {
                    const markerColor = (isString(ds.markerColor) ? ds.markerColor : null) || col;
                    drawEndpointMarker(context, xValue, yValue, markerColor);
                }
            }
        }
    });
};

const drawChartData = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, dims: ChartDimensions, geometry: RenderGeometry): void => {
    const valueViewport = getValueViewport(scene, dims);
    const chartType = scene.state.chartOptions.chartType;
    const wantsOhlc = scene.buffers.isOhlcRenderingType(chartType) || isOhlcChartType(chartType);
    const renderableOhlc = wantsOhlc ? scene.buffers.getRenderableOhlcBuffers() : null;

    context.save();
    clipToPlotArea(scene, context, dims);

    try {
        if (renderableOhlc && scene.state.dataLength > 0) {
            drawCandlesticks(scene, context, dims, geometry, renderableOhlc);
        } else {
            const seriesValues = scene.buffers.getValueBufferForRendering?.() ?? scene.state.values;
            const points = calculateVisiblePoints(scene, seriesValues, scene.state.dataLength, dims, geometry);
            if (points.length > 0 && hasVisiblePointBuffers(points)) {
                const baseline = valueViewport.top + valueViewport.height;
                const primaryColor = resolvePrimarySeriesColor(scene);
                if (chartType === 'area') drawArea(scene, context, points, dims, primaryColor);
                else if (chartType === 'deviation') drawDeviation(scene, context, points, dims, geometry);
                else if (chartType === 'bar') drawBars(scene, context, points, baseline, primaryColor, geometry);
                else if (chartType === 'precision-line') drawLine(context, points, primaryColor, { timestamps: scene.state.timestamps, intervalMs: scene.state.chartOptions.expectedSampleIntervalMs });
                else drawSpline(context, points, primaryColor, { timestamps: scene.state.timestamps, intervalMs: scene.state.chartOptions.expectedSampleIntervalMs });
            }
        }
        drawMultiLineData(scene, context, dims, geometry);
    } finally {
        context.restore();
    }
};

export { drawBars, drawChartData, drawCandlesticks, drawDeviation, drawLine, drawMultiLineData, drawSpline, resolveCandlestickPalette, resolvePrimarySeriesColor };
