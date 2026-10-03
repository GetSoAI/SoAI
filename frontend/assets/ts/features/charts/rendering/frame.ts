/* SoAI - Charts feature frame [frontend/assets/ts/features/charts/rendering/frame.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import { drawRoundedRect, getChartCornerRadii, getChartCornerRadius, hexToRgba } from '@features/charts/rendering/primitives.ts';
import type { ChartDimensions } from '@features/charts/rendering/renderingModels.ts';

const { max } = Math;

const drawChartFrame = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, dims?: ChartDimensions, options?: { rounded?: boolean }): void => {
    const actualDims = dims || scene.geometry.getChartDimensions();
    const { top, left, chartWidth: chartWidthValue, chartHeight: chartHeightValue } = actualDims;
    const chartWidth = Number(chartWidthValue) || 0;
    const chartHeight = Number(chartHeightValue) || 0;
    if (chartWidth <= 0 || chartHeight <= 0) return;
    const lineWidth = scene.geometry.getCssPixelSize?.(1) ?? 1;
    const inset = lineWidth / 2;
    context.save();
    context.lineWidth = lineWidth;
    const theme = scene.geometry.getThemeStyles();
    const colors = scene.state.chartOptions.colors;
    context.strokeStyle = theme?.axisGuideColor || colors.grid || colors.textSecondary || colors.text || colors.background || '';
    context.setLineDash([]);
    const rounded = options?.rounded !== false;
    const element = scene.state.element;
    if (rounded && !element) {
        throw new Error('Chart requires an element to resolve corner radii');
    }
    if (rounded && !(element instanceof HTMLElement)) {
        throw new Error('Chart element must be an HTMLElement to resolve corner radii');
    }
    const radius = rounded && element ? max(0, getChartCornerRadius(element) - inset) : 0;
    const frameRadii = {
        tl: radius,
        tr: radius,
        br: radius,
        bl: radius
    };
    drawRoundedRect(context, left + inset, top + inset, chartWidth - lineWidth, chartHeight - lineWidth, frameRadii);
    context.stroke();
    context.restore();
};

const tracePlotArea = (scene: ChartRenderingScene, context: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D, dims: ChartDimensions): { x: number; y: number; width: number; height: number } => {
    const lineWidth = scene.geometry.getCssPixelSize?.(1) ?? 1;
    const inset = lineWidth / 2;
    const element = scene.state.element;
    if (!element) throw new Error('Chart requires an element to resolve corner radii');
    const radii = getChartCornerRadii(element);
    const area = { x: dims.left + inset, y: dims.top + inset, width: dims.chartWidth - lineWidth, height: dims.chartHeight - lineWidth };
    drawRoundedRect(context, area.x, area.y, area.width, area.height, { tl: max(0, (radii.tl || 0) - inset), tr: max(0, (radii.tr || 0) - inset), br: max(0, (radii.br || 0) - inset), bl: max(0, (radii.bl || 0) - inset) });
    return area;
};

const clipToPlotArea = (scene: ChartRenderingScene, context: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D, dims: ChartDimensions): { x: number; y: number; width: number; height: number } => {
    const area = tracePlotArea(scene, context, dims);
    context.clip();
    return area;
};

const resolvePlotBackground = (scene: ChartRenderingScene): string => {
    const theme = scene.geometry.getThemeStyles();
    const colors = scene.state.chartOptions.colors;
    return theme?.plotBackground || hexToRgba(theme?.background || colors.background || colors.textSecondary || colors.text || colors.grid || '', 0.08);
};

export { clipToPlotArea, drawChartFrame, resolvePlotBackground };
