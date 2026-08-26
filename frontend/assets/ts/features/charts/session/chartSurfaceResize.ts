/* SoAI - Chart surface pixel sizing [frontend/assets/ts/features/charts/session/chartSurfaceResize.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { resolveCanvasRenderPixelRatio } from '@core/layout/canvasGeometry.ts';
import type { ChartSurfaceState } from '@features/charts/session/chartState.ts';

interface ChartSurfaceResizeCallbacks {
    afterResize(): void;
}

const resizeChartSurface = (surface: ChartSurfaceState, callbacks: ChartSurfaceResizeCallbacks, retry: () => void): boolean => {
    const bounds = measureLayoutBox(surface.element);
    const width = Math.max(0, bounds.width);
    const height = Math.max(0, bounds.height);
    if (width === 0 || height === 0) {
        if (surface.pendingResizeFrame === null) {
            surface.pendingResizeFrame = getRequestAnimationFrame()(() => {
                surface.pendingResizeFrame = null;
                const nextBounds = measureLayoutBox(surface.element);
                if (Math.max(0, nextBounds.width) > 0 && Math.max(0, nextBounds.height) > 0) retry();
            });
        }
        return false;
    }
    if (surface.pendingResizeFrame !== null) {
        getCancelAnimationFrame()(surface.pendingResizeFrame);
        surface.pendingResizeFrame = null;
    }
    const renderPixelRatio = resolveCanvasRenderPixelRatio(surface.element);
    const maxDimension = 16384;
    const scaledWidth = Math.min(Math.round(width * renderPixelRatio), maxDimension);
    const scaledHeight = Math.min(Math.round(height * renderPixelRatio), maxDimension);
    const interactionBounds = surface.canvasLayers.interaction ? measureLayoutBox(surface.canvasLayers.interaction) : null;
    const interactionWidth = Math.min(Math.round(Math.max(0, interactionBounds?.width ?? width) * renderPixelRatio), maxDimension);
    const interactionHeight = Math.min(Math.round(Math.max(0, interactionBounds?.height ?? height) * renderPixelRatio), maxDimension);
    const previous = surface.canvasDimensions;
    const previousInteraction = surface.interactionCanvasDimensions;
    if (previous.width === scaledWidth && previous.height === scaledHeight && previous.dpr === renderPixelRatio && previousInteraction.width === interactionWidth && previousInteraction.height === interactionHeight && previousInteraction.dpr === renderPixelRatio && surface.canvasLayers.interaction?.width === interactionWidth && surface.canvasLayers.interaction?.height === interactionHeight) return false;
    surface.canvasDimensions = { width: scaledWidth, height: scaledHeight, dpr: renderPixelRatio };
    surface.interactionCanvasDimensions = { width: interactionWidth, height: interactionHeight, dpr: renderPixelRatio };
    for (const canvas of [surface.canvasLayers.static, surface.canvasLayers.data]) {
        if (!canvas) continue;
        canvas.width = scaledWidth;
        canvas.height = scaledHeight;
    }
    if (surface.canvasLayers.interaction) {
        surface.canvasLayers.interaction.width = interactionWidth;
        surface.canvasLayers.interaction.height = interactionHeight;
    }
    for (const context of Object.values(surface.contexts)) context?.setTransform(renderPixelRatio, 0, 0, renderPixelRatio, 0, 0);
    if (surface.offscreenCanvas) {
        surface.offscreenCanvas.width = scaledWidth;
        surface.offscreenCanvas.height = scaledHeight;
        surface.offscreenContext?.setTransform(renderPixelRatio, 0, 0, renderPixelRatio, 0, 0);
    }
    callbacks.afterResize();
    return true;
};

export { resizeChartSurface };
export type { ChartSurfaceResizeCallbacks };
