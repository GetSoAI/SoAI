/* SoAI - Charts feature rendering models [frontend/assets/ts/features/charts/rendering/renderingModels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface AxisBreakpoint {
    width: number;
    labels: number;
}

interface ChartDimensions {
    top: number;
    left: number;
    chartWidth: number;
    chartHeight: number;
    width: number;
    height: number;
    right: number;
}

interface CanvasSize {
    width: number;
    height: number;
}

interface TimeWindow {
    startTs: number;
    endTs: number;
    span: number;
}

interface RenderGeometry {
    baseLeft: number;
    spacing: number;
    effectiveWidth: number;
    rightBoundary: number;
    visibleCount: number;
    originX: number;
    timeWindow: TimeWindow | null;
    span: number;
    chartWidth: number;
    nearTail: boolean;
    appliedMarginSlots: number;
}

interface ValueViewport {
    top: number;
    height: number;
    bottom: number;
}

interface YAxisTick {
    value: number;
    label: string;
    y: number;
}

interface XAxisTick {
    x: number;
    timestamp: number;
    label: string;
    textWidth: number;
}

interface AxisCache {
    key: string;
    yTicks: YAxisTick[];
    xTicks: XAxisTick[];
}

interface CornerRadii {
    tl: number;
    tr: number;
    br: number;
    bl: number;
}

export type { AxisBreakpoint, ChartDimensions, CanvasSize, TimeWindow, RenderGeometry, ValueViewport, YAxisTick, XAxisTick, AxisCache, CornerRadii };
