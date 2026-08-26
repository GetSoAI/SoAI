/* SoAI - Charts feature layers [frontend/assets/ts/features/charts/rendering/layers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getRenderGeometry } from '@features/charts/layout/geometry.ts';
import { computeAxisCache, drawAxes, drawGrid } from '@features/charts/rendering/axes.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import { drawChartFrame } from '@features/charts/rendering/frame.ts';
import { drawCrosshair, drawLegend } from '@features/charts/rendering/overlays.ts';
import { drawRoundedRect, getChartCornerRadii, hexToRgba } from '@features/charts/rendering/primitives.ts';
import { drawChartData } from '@features/charts/rendering/series/service.ts';
import { renderChartDataState } from '@features/charts/rendering/stateRenderer.ts';

const { max } = Math;

const renderStaticLayer = (scene: ChartRenderingScene): void => {
    const { width, height } = scene.geometry.getCanvasSize();
    if (!width || !height) return;

    const context = scene.surface.offscreenContext || scene.surface.contexts['static'];
    if (!context) return;
    const usingOffscreen = context === scene.surface.offscreenContext && scene.surface.offscreenCanvas;
    context.clearRect(0, 0, width, height);

    const baseBg = scene.buffers.resolveCanvasBaseBackground() ?? scene.surface.canvasBaseBackground;
    if (baseBg) {
        context.save();
        context.fillStyle = baseBg;
        context.fillRect(0, 0, width, height);
        context.restore();
    }

    const dims = scene.geometry.getChartDimensions();
    const geometry = getRenderGeometry(scene.state, scene.geometry, dims);
    const theme = scene.geometry.getThemeStyles();
    if (dims.chartWidth > 0 && dims.chartHeight > 0) {
        const lineWidth = scene.geometry.getCssPixelSize?.(1) ?? 1;
        const inset = lineWidth / 2;
        const bgX = dims.left + inset;
        const bgY = dims.top + inset;
        const bgW = dims.chartWidth - lineWidth;
        const bgH = dims.chartHeight - lineWidth;
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
        context.save();
        drawRoundedRect(context, bgX, bgY, bgW, bgH, clipRadii);
        context.clip();
        const colors = scene.state.chartOptions.colors;
        context.fillStyle = theme?.plotBackground || hexToRgba(theme?.background || colors.background || colors.textSecondary || colors.text || colors.grid || '', 0.08);
        context.fillRect(bgX, bgY, bgW, bgH);
        computeAxisCache(scene, context, dims, geometry);
        drawGrid(scene, context, dims, geometry);
        context.restore();
    } else {
        computeAxisCache(scene, context, dims, geometry);
        drawGrid(scene, context, dims, geometry);
    }

    if (usingOffscreen && scene.surface.offscreenCanvas && scene.surface.offscreenCanvas.width && scene.surface.offscreenCanvas.height && scene.surface.contexts.static) {
        const targetContext = scene.surface.contexts.static;
        targetContext.clearRect(0, 0, width, height);
        targetContext.drawImage(scene.surface.offscreenCanvas, 0, 0, width, height);
    }
};

const renderDataLayer = (scene: ChartRenderingScene): void => {
    const { data: context } = scene.surface.contexts;
    const { width, height } = scene.geometry.getCanvasSize();
    if (!context || !width || !height) return;
    context.clearRect(0, 0, width, height);

    if (renderChartDataState(scene, context, width, height)) {
        return;
    }
    drawChartData(scene, context);
    drawAxes(scene, context);
    drawChartFrame(scene, context);
    if (scene.state.chartOptions.enableCrosshair && scene.state.crosshair.visible) drawCrosshair(scene, context);
    drawLegend(scene, context);
};

const renderInteractionLayer = (scene: ChartRenderingScene): void => {
    const { interaction: context } = scene.surface.contexts;
    const { width, height } = scene.geometry.getCanvasSize();
    if (!context || !width || !height) return;
    context.clearRect(0, 0, width, height);
};

export { renderStaticLayer, renderDataLayer, renderInteractionLayer };
