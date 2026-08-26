/* SoAI - Charts feature chart rendering host [frontend/assets/ts/features/charts/rendering/chartRenderingHost.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartOptions, ChartTimestampFormatter, CrosshairState, Dataset, ThemeStyles, VisiblePointsCache } from '@features/charts/chartTypes.ts';
import type { ChartPadding, PanState, RenderBuffers, Scale, SlotMetrics, VisibleRange, VisibleRangeStats } from '@features/charts/component/chartComponentTypes.ts';
import type { AxisCache, ChartDimensions, TimeWindow } from '@features/charts/rendering/renderingModels.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ComponentOptionsRecord } from '@core/BaseComponent.ts';

type CanvasContexts = {
    static: CanvasRenderingContext2D | null;
    data: CanvasRenderingContext2D | null;
    interaction: CanvasRenderingContext2D | null;
};

type RedrawRequest = Readonly<{
    static?: boolean | undefined;
    data?: boolean | undefined;
    interaction?: boolean | undefined;
}>;

interface ChartRenderingStatePort {
    element: HTMLElement | null;
    options: ComponentOptionsRecord<ChartOptions>;
    chartOptions: ChartOptions;

    dataLength: number;
    datasets: Dataset[];
    values: Float64Array;
    timestamps: Float64Array;
    scale: Scale;
    visibleRange: VisibleRange;
    visibleRangeStats: VisibleRangeStats;
    pan: PanState;
    visiblePointsCache: VisiblePointsCache | null;
    axisCache: AxisCache | null;
    legendData: Record<string, JsonValue | null | undefined>;
    padding: ChartPadding;
    crosshair: CrosshairState;
}

interface ChartRenderingSurfacePort {
    contexts: CanvasContexts;
    offscreenCanvas: OffscreenCanvas | null;
    offscreenContext: OffscreenCanvasRenderingContext2D | null;
    canvasBaseBackground: string | null;
    isHistoricalDataLoading: boolean;
    scheduleLoadingRedraw(): void;
}

interface ChartRenderingGeometryPort {
    getChartDimensions: () => ChartDimensions;
    getCanvasSize: () => { width: number; height: number };
    getCssPixelSize?: ((px: number) => number) | undefined;
    getThemeStyles: () => ThemeStyles;
    applyAlphaToColor?: ((color: string, alpha: number) => string) | undefined;
    getPixelsPerBar: () => number | null;
    getEffectiveDataLength: () => number;
    getSlotMetrics: () => SlotMetrics;
    getMaxOffsetForMetrics: (metrics?: SlotMetrics | null) => number;
    getVisibleTimeSpan?: (() => number) | undefined;
    getVisibleTimeWindow: () => TimeWindow | null;
}

interface ChartRenderingFormatPort {
    valueToPixel: (value: number, height: number, top: number) => number;
    formatValue: (value: number) => string;
    formatTimestamp: (timestamp: number, mode?: ChartTimestampFormatter | string | null | undefined) => string;
    formatAxisTimestamp?: ((timestamp: number, spanMs: number) => string) | undefined;
    formatDetailedTimestamp: (timestamp: number, options?: JsonObject | null | undefined) => string;
}

interface ChartRenderingBufferPort {
    ensureRenderBufferCapacity: (size: number) => RenderBuffers;
    requestRedraw: (request?: RedrawRequest) => void;

    resolveDynamicPrimaryColor?: (() => string | null) | undefined;
    resolveCanvasBaseBackground: () => string;
    isOhlcRenderingType: (currentTime?: string) => boolean;
    getRenderableOhlcBuffers: () => {
        open: Float64Array;
        high: Float64Array;
        low: Float64Array;
        close: Float64Array;
    } | null;
    getValueBufferForRendering?: (() => Float64Array) | undefined;
}

interface ChartRenderingScene {
    state: ChartRenderingStatePort;
    surface: ChartRenderingSurfacePort;
    geometry: ChartRenderingGeometryPort;
    format: ChartRenderingFormatPort;
    buffers: ChartRenderingBufferPort;
}

export type { ChartRenderingBufferPort, ChartRenderingFormatPort, ChartRenderingGeometryPort, ChartRenderingScene, ChartRenderingStatePort, ChartRenderingSurfacePort };
