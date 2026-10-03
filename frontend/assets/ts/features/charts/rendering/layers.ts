/* SoAI - Charts feature layers [frontend/assets/ts/features/charts/rendering/layers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { monotonicMs } from '@core/time/clock.ts';
import { computeAxisCache, drawAxes, drawGrid } from '@features/charts/rendering/axes.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import { clipToPlotArea, drawChartFrame, resolvePlotBackground } from '@features/charts/rendering/frame.ts';
import { drawCrosshair, drawLegend } from '@features/charts/rendering/overlays.ts';
import { drawHistoryPreview } from '@features/charts/rendering/preview/historyPreview.ts';
import { drawChartData } from '@features/charts/rendering/series/service.ts';
import { renderChartDataState } from '@features/charts/rendering/stateRenderer.ts';

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
    const geometry = scene.geometry.getRenderGeometry(dims);
    if (dims.chartWidth > 0 && dims.chartHeight > 0) {
        context.save();
        const area = clipToPlotArea(scene, context, dims);
        context.fillStyle = resolvePlotBackground(scene);
        context.fillRect(area.x, area.y, area.width, area.height);
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
    const dims = scene.geometry.getChartDimensions();
    const geometry = scene.geometry.getRenderGeometry(dims);
    if (geometry) {
        drawChartData(scene, context, dims, geometry);
        drawHistoryPreview(scene, context, dims, geometry, scene.preview.frame(monotonicMs()));
    }
    drawAxes(scene, context, dims, geometry);
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
