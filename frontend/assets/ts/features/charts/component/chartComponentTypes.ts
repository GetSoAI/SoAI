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
    startTs: number;
    endTs: number;
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

interface PanState {
    isDragging: boolean;
    lastX: number;
    lastY: number;
    travelPx: number;
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
    startMsPerPx: number;
    anchorX: number;
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
    startTs: number | null;
    endTs: number | null;
}

interface ChartRuntimeInstance {
    acquireLayers: (names?: readonly LayerName[], options?: { zBase?: number }) => RuntimeLayer[];
    releaseLayers: (layers: readonly RuntimeLayer[] | null) => void;
}

interface ChartTimeRangeChangeDetail {
    start: number;
    end: number;
}

type ComponentEventDetail = CrosshairState | ChartTimeRangeChangeDetail | null;
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

export type { CanvasContexts, CanvasDimensions, CanvasLayers, ChartPadding, ChartRuntimeInstance, ColorComponents, ComponentEventDetail, EventHandler, NeedsRedraw, OhlcData, PanState, RedrawRequest, RenderBuffers, RuntimeLayer, Scale, ThemeColorFlags, TimeRange, VisiblePointsCache, VisibleRange, VisibleRangeStats, XAxisDragState, YAxisDragState };
