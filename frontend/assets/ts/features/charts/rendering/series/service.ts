/* SoAI - Charts feature series service [frontend/assets/ts/features/charts/rendering/series/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { Dataset } from '@features/charts/chartTypes.ts';
import { isOhlcChartType } from '@features/charts/chartTypeNormalization.ts';
import type { OhlcData } from '@features/charts/component/chartComponentTypes.ts';
import { getRenderGeometry, getXForVisibleIndex } from '@features/charts/layout/geometry.ts';
import { getValueViewport } from '@features/charts/rendering/axes.ts';
import { drawRoundedRect, getChartCornerRadii, hexToRgba } from '@features/charts/rendering/primitives.ts';
import type { ChartDimensions, RenderGeometry } from '@features/charts/rendering/renderingModels.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import { hasVisiblePointBuffers } from '@features/charts/rendering/series/guards.ts';
import { drawEndpointMarker } from '@features/charts/rendering/series/effects.ts';
import { calculateVisiblePoints, findLatestValidIndex } from '@features/charts/rendering/series/state.ts';
import { drawArea, drawBars, drawDeviation, drawLine, drawSpline } from '@features/charts/rendering/series/view.ts';

const { min, max } = Math;
const { isFinite: isFiniteNumber } = Number;

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

const drawCandlesticks = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, dims: ChartDimensions, geometry: RenderGeometry, ohlc?: OhlcData | null): void => {
    const valueViewport = getValueViewport(scene, dims);
    const { height, top } = valueViewport;
    const { displayCount: displayCountValue, offsetFraction, start } = scene.state.visibleRange;
    const displayCount = Number(displayCountValue) || 0;
    if (displayCount <= 0 || !ohlc) return;

    const spacing = geometry.spacing || (displayCount > 1 ? dims.chartWidth / max(1, displayCount - 1) : dims.chartWidth);
    const bodyWidth = max(scene.geometry.getCssPixelSize?.(1.4) ?? 1.4, min(spacing * 0.6, (scene.geometry.getPixelsPerBar?.() ?? spacing) * 0.9));
    const halfWidth = bodyWidth / 2;
    const limit = min(displayCount, scene.state.dataLength - start);
    const originX = (geometry.originX ?? geometry.baseLeft ?? dims.left) - spacing * offsetFraction;
    const { open: op, high: hi, low: lo, close: cl } = ohlc;
    const isLog = scene.state.chartOptions.scaleType === 'logarithmic';
    const css1 = scene.geometry.getCssPixelSize?.(1) ?? 1;
    const css11 = max(scene.geometry.getCssPixelSize?.(1.1) ?? 1.1, bodyWidth * 0.12);
    const candlestickPalette = resolveCandlestickPalette(scene);

    context.save();
    context.lineCap = 'butt';

    for (let visibleIndex = 0; visibleIndex < limit; visibleIndex++) {
        const dataIndex = start + visibleIndex;
        const open = op[dataIndex];
        const high = hi[dataIndex];
        const low = lo[dataIndex];
        const close = cl[dataIndex];
        if (open === undefined || high === undefined || low === undefined || close === undefined) continue;
        if (!isFiniteNumber(open) || !isFiniteNumber(high) || !isFiniteNumber(low) || !isFiniteNumber(close)) continue;
        if (isLog && (open <= 0 || high <= 0 || low <= 0 || close <= 0)) continue;
        const color = close >= open ? candlestickPalette.up : candlestickPalette.down;
        const xCoordinate = getXForVisibleIndex(scene.state, visibleIndex, displayCount, originX, spacing, geometry, dims);
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

const drawOhlcBars = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, dims: ChartDimensions, geometry?: RenderGeometry, ohlc?: OhlcData | null): void => {
    const actualGeometry = geometry || getRenderGeometry(scene.state, scene.geometry, dims);
    const valueViewport = getValueViewport(scene, dims);
    const { height, top } = valueViewport;
    const { displayCount: displayCountValue, offsetFraction, start } = scene.state.visibleRange;
    const displayCount = Number(displayCountValue) || 0;
    if (displayCount <= 0 || !ohlc) return;

    const spacing = actualGeometry.spacing || (displayCount > 1 ? dims.chartWidth / max(1, displayCount - 1) : dims.chartWidth);
    const tickWidth = max(scene.geometry.getCssPixelSize?.(2) ?? 2, min(spacing * 0.4, (scene.geometry.getPixelsPerBar?.() ?? spacing) * 0.5));
    const halfTick = tickWidth / 2;
    const limit = min(displayCount, scene.state.dataLength - start);
    const originX = (actualGeometry.originX ?? actualGeometry.baseLeft ?? dims.left) - spacing * offsetFraction;
    const { open: op, high: hi, low: lo, close: cl } = ohlc;
    const isLog = scene.state.chartOptions.scaleType === 'logarithmic';
    const lineWidth = max(scene.geometry.getCssPixelSize?.(1.2) ?? 1.2, 1.2);
    const colors = scene.state.chartOptions.colors;
    const upColor = colors.statusGreen || colors.primary || colors.secondary || colors.textSecondary || colors.text || colors.grid || colors.background || '';
    const downColor = colors.statusRed || colors.primary || colors.secondary || colors.textSecondary || colors.text || colors.grid || colors.background || '';

    context.save();
    context.lineCap = 'butt';
    context.lineWidth = lineWidth;
    for (let visibleIndex = 0; visibleIndex < limit; visibleIndex++) {
        const dataIndex = start + visibleIndex;
        const open = op[dataIndex];
        const high = hi[dataIndex];
        const low = lo[dataIndex];
        const close = cl[dataIndex];
        if (open === undefined || high === undefined || low === undefined || close === undefined) continue;
        if (!isFiniteNumber(open) || !isFiniteNumber(high) || !isFiniteNumber(low) || !isFiniteNumber(close)) continue;
        if (isLog && (open <= 0 || high <= 0 || low <= 0 || close <= 0)) continue;

        context.strokeStyle = hexToRgba(close >= open ? upColor : downColor, 0.95);
        const xCoordinate = getXForVisibleIndex(scene.state, visibleIndex, displayCount, originX, spacing, actualGeometry, dims);
        const highY = scene.format.valueToPixel(high, height, top);
        const lowY = scene.format.valueToPixel(low, height, top);
        const openY = scene.format.valueToPixel(open, height, top);
        const closeY = scene.format.valueToPixel(close, height, top);

        context.beginPath();
        context.moveTo(xCoordinate, highY);
        context.lineTo(xCoordinate, lowY);
        context.moveTo(xCoordinate - halfTick, openY);
        context.lineTo(xCoordinate, openY);
        context.moveTo(xCoordinate, closeY);
        context.lineTo(xCoordinate + halfTick, closeY);
        context.stroke();
    }
    context.restore();
};

const drawMultiLineData = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, dims: ChartDimensions, geometry?: RenderGeometry): void => {
    const actualDims = dims;
    const actualGeometry = geometry || getRenderGeometry(scene.state, scene.geometry, actualDims);
    const colors = scene.state.chartOptions.colors;
    const { secondary, tertiary, quaternary } = colors;
    const defaultPalette = [secondary, tertiary, quaternary].filter((color): color is string => Boolean(color));
    const defaultLineColor = secondary || colors.primary || '';

    scene.state.datasets.forEach((ds: Dataset, index: number) => {
        const vals = ds?.values;
        if (!vals?.length) return;
        const pts = calculateVisiblePoints(scene, vals, vals.length, actualDims, actualGeometry);
        if (!pts.length) return;
        if (!hasVisiblePointBuffers(pts)) return;
        const defaultColor = defaultPalette.length > 0 ? defaultPalette[index % defaultPalette.length] : undefined;
        const col = (isString(ds.color) ? ds.color : null) || defaultColor || secondary || defaultLineColor;
        drawLine(context, pts, col);
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

const drawChartData = (scene: ChartRenderingScene, context: CanvasRenderingContext2D): void => {
    const dims = scene.geometry.getChartDimensions();
    const geometry = getRenderGeometry(scene.state, scene.geometry, dims);
    const valueViewport = getValueViewport(scene, dims);
    const chartType = scene.state.chartOptions.chartType;
    const colors = scene.state.chartOptions.colors;
    const wantsOhlc = scene.buffers.isOhlcRenderingType(chartType) || isOhlcChartType(chartType);
    const renderableOhlc = wantsOhlc ? scene.buffers.getRenderableOhlcBuffers() : null;

    context.save();
    const lineWidth = scene.geometry.getCssPixelSize?.(1) ?? 1;
    const inset = lineWidth / 2;
    const element = scene.state.element;
    if (!element) {
        throw new Error('Chart requires an element to resolve corner radii');
    }
    const radii = getChartCornerRadii(element);
    const clipRadii = {
        tl: max(0, (radii.tl || 0) - inset),
        tr: max(0, (radii.tr || 0) - inset),
        br: max(0, (radii.br || 0) - inset),
        bl: max(0, (radii.bl || 0) - inset)
    };
    drawRoundedRect(context, dims.left + inset, dims.top + inset, dims.chartWidth - lineWidth, dims.chartHeight - lineWidth, clipRadii);
    context.clip();

    const defaultLineColor = colors.secondary || colors.primary || '';

    try {
        if (renderableOhlc && scene.state.dataLength > 0) {
            if (chartType === 'ohlcbars') {
                drawOhlcBars(scene, context, dims, geometry, renderableOhlc);
            } else {
                drawCandlesticks(scene, context, dims, geometry, renderableOhlc);
            }
        } else {
            const seriesValues = scene.buffers.getValueBufferForRendering?.() ?? scene.state.values;
            const points = calculateVisiblePoints(scene, seriesValues, scene.state.dataLength, dims, geometry);
            if (points.length > 0 && hasVisiblePointBuffers(points)) {
                const baseline = valueViewport.top + valueViewport.height;
                const dynamicPrimary = scene.buffers.resolveDynamicPrimaryColor?.();
                const primaryColor = dynamicPrimary && isString(dynamicPrimary) ? dynamicPrimary : defaultLineColor || colors.tertiary || colors.quaternary || colors.textSecondary || colors.text || '';
                if (chartType === 'area') drawArea(scene, context, points, dims, primaryColor);
                else if (chartType === 'deviation') drawDeviation(scene, context, points, dims, geometry);
                else if (chartType === 'bar') drawBars(scene, context, points, baseline, primaryColor, geometry);
                else if (chartType === 'precision-line') drawLine(context, points, primaryColor);
                else drawSpline(context, points, primaryColor);
            }
        }
        drawMultiLineData(scene, context, dims, geometry);
    } finally {
        context.restore();
    }
};

export { drawBars, drawChartData, drawCandlesticks, drawDeviation, drawLine, drawMultiLineData, drawOhlcBars, drawSpline };
