/* SoAI - Charts feature axes [frontend/assets/ts/features/charts/rendering/axes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { AXIS_FONT_SIZE, MIN_LABEL_GAP, Y_AXIS_LABEL_GAP, Y_AXIS_OUTER_PADDING, getXAxisFont, resolveVerticalContentInset } from '@features/charts/rendering/axisrendering/constants.ts';
import { generateXAxisTicks, generateYAxisTicks } from '@features/charts/rendering/axisrendering/service.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import { drawCoordinateLabel, requireThemeColor, resolveThemeColor } from '@features/charts/rendering/primitives.ts';
import type { AxisCache, ChartDimensions, RenderGeometry, ValueViewport } from '@features/charts/rendering/renderingModels.ts';

const { isFinite: isFin } = Number;
const { max, min } = Math;

type ChartValueViewportScene = Pick<ChartRenderingScene, 'state' | 'geometry'>;

const getValueViewport = (scene: ChartValueViewportScene, dims: ChartDimensions = scene.geometry.getChartDimensions()): ValueViewport => {
    const chartHeight = max(0, Number(dims['chartHeight']) || 0);
    const inset = resolveVerticalContentInset(chartHeight);
    const top = (isFin(dims['top']) ? dims['top'] : 0) + inset;
    const height = max(1, chartHeight - inset * 2);
    return { top, height, bottom: top + height };
};

const computeAxisCache = (scene: ChartRenderingScene, context: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D, dims: ChartDimensions, geometry: RenderGeometry | null): AxisCache => {
    const scale = scene.state.scale;
    const yTicks = generateYAxisTicks(scene, dims, getValueViewport(scene, dims));
    const cacheKey = [scene.state.dataLength, scale.min, scale.max, dims.left, dims.width, dims.chartWidth, dims.chartHeight, yTicks.map((tick) => tick.label).join('\u001f'), scene.state.options.scaleType, geometry?.rightEdgeTs, geometry?.msPerPx].join('|');

    const cachedAxis = scene.state.axisCache;
    if (cachedAxis && cachedAxis.key === cacheKey) {
        return cachedAxis;
    }

    const previousFont = context.font;
    context.font = getXAxisFont();
    const xTicks = geometry ? generateXAxisTicks(scene, context, dims, geometry) : [];
    context.font = previousFont;

    const axisCache: AxisCache = { key: cacheKey, yTicks, xTicks };
    scene.state.axisCache = axisCache;
    return axisCache;
};

const drawGrid = (scene: ChartRenderingScene, context: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D, actualDims: ChartDimensions, actualGeometry: RenderGeometry | null): void => {
    const chartWidth = Number(actualDims['chartWidth']) || 0;
    const chartHeight = Number(actualDims['chartHeight']) || 0;
    const top = Number(actualDims['top']) || 0;
    const left = Number(actualDims['left']) || 0;
    if (chartWidth <= 0 || chartHeight <= 0) {
        return;
    }

    const { xTicks, yTicks } = computeAxisCache(scene, context, actualDims, actualGeometry);
    if (!isArray(xTicks)) {
        throw new TypeError('Axis cache xTicks must be an array');
    }
    if (!isArray(yTicks)) {
        throw new TypeError('Axis cache yTicks must be an array');
    }

    const lineWidth = scene.geometry.getCssPixelSize?.(1) ?? 1;
    const inset = lineWidth / 2;
    const frameLeft = left + inset;
    const frameTop = top + inset;
    const frameBottom = top + chartHeight - inset;
    const gridRight = left + chartWidth - inset;

    context.save();
    context.lineWidth = lineWidth;
    context.setLineDash([2, 2]);
    const theme = scene.geometry.getThemeStyles();
    const colors = scene.state.chartOptions.colors;
    const axisGuide = resolveThemeColor(theme, colors, ['axisGuideColor', 'grid', 'textSecondary', 'text', 'background']);
    const isDark = theme?.isDark ?? null;
    context.strokeStyle = scene.geometry.applyAlphaToColor?.(axisGuide, isDark ? 0.32 : 0.45) ?? axisGuide;

    if (xTicks.length || yTicks.length) {
        context.beginPath();
        for (const tick of xTicks) {
            const drawX = max(frameLeft, min(gridRight, tick.x));
            context.moveTo(drawX, frameTop);
            context.lineTo(drawX, frameBottom);
        }
        for (const tick of yTicks) {
            const drawY = max(frameTop, min(frameBottom, tick.y));
            context.moveTo(frameLeft, drawY);
            context.lineTo(gridRight, drawY);
        }
        context.stroke();
    } else {
        context.strokeRect(frameLeft, frameTop, gridRight - frameLeft, frameBottom - frameTop);
    }
    context.restore();
};

const drawAxes = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, dims: ChartDimensions, geometry: RenderGeometry | null): void => {
    const chartWidth = Number(dims['chartWidth']) || 0;
    const chartHeight = Number(dims['chartHeight']) || 0;
    const top = Number(dims['top']) || 0;
    const left = Number(dims['left']) || 0;
    const { min: scaleMin, max: scaleMax } = scene.state.scale;
    if (scaleMin === null || scaleMax === null) {
        return;
    }

    const { yTicks, xTicks } = computeAxisCache(scene, context, dims, geometry);
    const theme = scene.geometry.getThemeStyles();
    const colors = scene.state.chartOptions.colors;
    const primaryAxisColor = resolveThemeColor(theme, colors, ['text', 'legendTextColor', 'textSecondary', 'background', 'axisGuideColor']);
    const axisTextColor = scene.state.scale.auto ? resolveThemeColor(theme, colors, ['textSecondary', 'axisGuideColor', 'text', 'background']) : primaryAxisColor;

    Object.assign(context, {
        fillStyle: axisTextColor,
        font: scene.state.scale.auto ? '12px sans-serif' : '600 12px sans-serif',
        textAlign: 'left',
        textBaseline: 'middle'
    });

    if (!isArray(yTicks)) {
        throw new TypeError('Axis cache yTicks must be an array');
    }
    const yAxisX = left + chartWidth + Y_AXIS_LABEL_GAP;
    const yAxisLabelWidth = max(1, dims.width - yAxisX - Y_AXIS_OUTER_PADDING);

    if (yTicks.length) {
        for (const tick of yTicks) {
            context.fillText(tick.label, yAxisX, max(top, min(top + chartHeight, tick.y)), yAxisLabelWidth);
        }
    } else {
        for (let index = 0; index <= 4; index += 1) {
            context.fillText(scene.format.formatValue(scaleMin + ((scaleMax - scaleMin) / 4) * (4 - index)), yAxisX, top + (chartHeight / 4) * index, yAxisLabelWidth);
        }
    }

    if (!scene.state.scale.auto) {
        Object.assign(context, {
            fillStyle: colors.primary || primaryAxisColor,
            font: '600 10px sans-serif',
            textAlign: 'left',
            textBaseline: 'bottom'
        });
        context.fillText(i18n.t('charts.manualScaleLabel'), yAxisX, top - AXIS_FONT_SIZE / 2 - MIN_LABEL_GAP);
    }

    if (!geometry || scene.state.dataLength === 0) {
        return;
    }

    Object.assign(context, {
        fillStyle: axisTextColor,
        font: getXAxisFont(),
        textAlign: 'center',
        textBaseline: 'top'
    });
    const bottomAxisPadding = scene.state.chartOptions.bottomAxisPadding;
    const labelBaseline = top + chartHeight + max(6, min(bottomAxisPadding - 12, (bottomAxisPadding - 12) * 0.5 + 12));
    const rightLimit = left + chartWidth;

    if (!isArray(xTicks)) {
        throw new TypeError('Axis cache xTicks must be an array');
    }
    for (const tick of xTicks) {
        context.fillText(tick.label, tick.x, labelBaseline);
    }

    if (scene.state.chartOptions.showAxisCoordinates && scene.state.crosshair.visible && scene.state.crosshair.timestamp) {
        const timeLabelResult = scene.format.formatTimestamp(scene.state.crosshair.timestamp, 'full');
        if (timeLabelResult && isString(timeLabelResult)) {
            const boxWidth = context.measureText(timeLabelResult).width + 24;
            const minX = left + boxWidth / 2;
            const boxCenterX = max(minX, min(scene.state.crosshair.x, max(minX, rightLimit - boxWidth / 2)));
            const boxY = labelBaseline - 10 / 2 + 5;

            drawCoordinateLabel(context, boxCenterX, boxY + 10 / 2, timeLabelResult, {
                bgColor: requireThemeColor(theme, 'crosshairValueBackground'),
                textColor: requireThemeColor(theme, 'crosshairValueTextColor'),
                font: `600 ${AXIS_FONT_SIZE}px sans-serif`,
                paddingX: 12,
                paddingY: 4
            });
        }
    }
};

export { computeAxisCache, drawGrid, drawAxes, getValueViewport, getXAxisFont };
