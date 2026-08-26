/* SoAI - Charts feature chart component types [frontend/assets/ts/features/charts/component/chartComponentTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartThemeFlagInput, CrosshairState, VisiblePointsCache } from '@features/charts/chartTypes.ts';
import type { LayerName } from '@features/charts/Runtime.ts';

interface ThemeColorFlags extends ChartThemeFlagInput {
    [key: string]: boolean | undefined;
}

interface RenderBuffers {
    capacity: number;
    x: Float64Array;
    y: Float64Array;
    value: Float64Array;
    valid: Uint8Array;
    index: Uint32Array;
}

interface VisibleRange {
    start: number;
    end: number;
    displayCount: number;
    totalSlots: number;
    marginSlots: number;
    offsetFraction: number;
}

interface VisibleRangeStats {
    min: number | null;
    max: number | null;
    sum: number;
    count: number;
}

interface Scale {
    min: number | null;
    max: number | null;
    auto: boolean;
}

interface ZoomState {
    level: number;
    targetLevel: number;
    minLevel: number;
    maxLevel: number;
    isAnimating: boolean;
    startTime: number;
    startLevel: number;
    wheelAccumulator: number;
}

interface PanState {
    offset: number;
    velocity: number;
    isDragging: boolean;
    lastX: number;
    lastY: number;
    isAtTail: boolean;
    startOffset: number;
    targetOffset: number;
    isZooming: boolean;
}

interface YAxisDragState {
    active: boolean;
    startY: number;
    startMin: number;
    startMax: number;
    startRange: number;
    startCenter: number;
    minRange: number;
}

interface XAxisDragState {
    active: boolean;
    startX: number;
    startZoomLevel: number;
    anchor: number;
    startPanOffset: number;
    startMetrics: SlotMetrics;
}

interface SlotMetrics {
    totalSlots: number;
    dataSlots: number;
    marginSlots: number;
}

interface OhlcData {
    open: Float64Array;
    high: Float64Array;
    low: Float64Array;
    close: Float64Array;
}

interface CanvasLayers {
    static: HTMLCanvasElement | null;
    data: HTMLCanvasElement | null;
    interaction: HTMLCanvasElement | null;
}

interface CanvasContexts {
    static: CanvasRenderingContext2D | null;
    data: CanvasRenderingContext2D | null;
    interaction: CanvasRenderingContext2D | null;
}

interface CanvasDimensions {
    width: number;
    height: number;
    dpr: number;
}

interface NeedsRedraw {
    static: boolean;
    data: boolean;
    interaction: boolean;
}

interface ChartPadding {
    top: number;
    right: number;
    bottom: number;
    left: number;
}

interface TimeRange {
    start: number;
    end: number;
    startTs: number | null;
    endTs: number | null;
}

interface ChartRuntimeInstance {
    acquireLayers: (names?: readonly LayerName[], options?: { zBase?: number }) => RuntimeLayer[];
    releaseLayers: (layers: readonly RuntimeLayer[] | null) => void;
}

interface ChartNeedHistoricalDataDetail {
    timestamp: number;
}

interface ChartTimeRangeChangeDetail {
    start: number;
    end: number;
}

interface ChartZoomChangeDetail {
    level: number;
    oldLevel: number;
    source?: string | undefined;
}

type ComponentEventDetail = CrosshairState | ChartNeedHistoricalDataDetail | ChartTimeRangeChangeDetail | ChartZoomChangeDetail | null;
type EventHandler = (data?: ComponentEventDetail | undefined) => void;

interface RedrawRequest {
    static?: boolean | undefined;
    data?: boolean | undefined;
    interaction?: boolean | undefined;
}

interface RuntimeLayer {
    canvas: HTMLCanvasElement;
    context: CanvasRenderingContext2D;
    name: LayerName;
}

interface ColorComponents {
    red: number;
    green: number;
    blue: number;
    alpha: number;
}

interface ViewportIntent {
    mode: string;
    source?: string | undefined;
    timestamp?: number | undefined;
    [key: string]: string | number | boolean | null | undefined;
}

export type { CanvasContexts, CanvasDimensions, CanvasLayers, ChartPadding, ChartRuntimeInstance, ColorComponents, ComponentEventDetail, EventHandler, NeedsRedraw, OhlcData, PanState, RedrawRequest, RenderBuffers, RuntimeLayer, Scale, SlotMetrics, ThemeColorFlags, TimeRange, ViewportIntent, VisiblePointsCache, VisibleRange, VisibleRangeStats, XAxisDragState, YAxisDragState, ZoomState };
