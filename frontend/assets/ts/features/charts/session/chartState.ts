/* SoAI - Chart domain state ownership [frontend/assets/ts/features/charts/session/chartState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { DEFAULT_CHART_PADDING } from '@core/charts/constants.ts';
import type { ChartOptions, CrosshairState, Dataset, OhlcValues, PointerState, TimestampFormatConfig } from '@features/charts/chartTypes.ts';
import { BASE_MAX_ZOOM_LEVEL, computeDynamicMinZoomLevel, DEFAULT_BOTTOM_AXIS_PADDING, DEFAULT_CHART_COLORS, DEFAULT_MAX_DATA_POINTS, DEFAULT_MAX_RIGHT_MARGIN_PX, DEFAULT_MAX_RIGHT_MARGIN_RATIO, DEFAULT_MIN_HEIGHT, DEFAULT_VERTICAL_SCALE_PADDING_RATIO, MAX_DATA_POINTS_HARD_LIMIT } from '@features/charts/component/chartComponentStatics.ts';
import type { CanvasContexts, CanvasDimensions, CanvasLayers, ChartPadding, ChartRuntimeInstance, OhlcData, PanState, RenderBuffers, RuntimeLayer, Scale, ThemeColorFlags, TimeRange, ViewportIntent, VisibleRange, VisibleRangeStats, XAxisDragState, YAxisDragState, ZoomState } from '@features/charts/component/chartComponentTypes.ts';
import { normalizeChartType, normalizeClampedFloat, normalizeClampedInt, normalizeScaleBounds, normalizeScaleType, normalizeValuePrecision } from '@features/charts/component/state/actions.ts';
import { mergeColorPalette, resolvePaletteFromCssAndOverrides, sanitizeThemeFlags } from '@features/charts/component/state/service.ts';
import { normalizeTimestampFormat } from '@features/charts/component/data/timeFormatting.ts';

interface ChartConfigurationState {
    options: ChartOptions;
    padding: ChartPadding;
    themeColorFlags: ThemeColorFlags;
    timestampFormatConfig: TimestampFormatConfig;
}

interface ChartSeriesState {
    timestamps: Float64Array;
    values: Float64Array;
    renderBuffers: RenderBuffers;
    dataLength: number;
    datasets: Dataset[];
    dataStructure: string;
    sourceSeriesMode: string;
    ohlc: OhlcData | null;
    heikin: OhlcData | null;
    heikinDirtyIndex: number;
    heikinValidLength: number;
    ohlcScratch: OhlcValues;
}

interface ChartViewportState {
    visibleRange: VisibleRange;
    visibleRangeStats: VisibleRangeStats;
    scale: Scale;
    baseBarPixelWidth: number;
    zoom: ZoomState;
    pan: PanState;
    yAxisMinRange: number;
    yAxisDrag: YAxisDragState;
    xAxisDrag: XAxisDragState;
    viewportIntent: ViewportIntent | null;
    pendingViewportIntent: ViewportIntent | null;
    suspendIntentRecording: boolean;
    isHistoricalDataLoading: boolean;
    lastHistoricalRequestTimestamp: number | null;
    lastEmittedTimeRange: TimeRange;
}

interface ChartSurfaceState {
    element: HTMLElement;
    canvasLayers: CanvasLayers;
    canvasDimensions: CanvasDimensions;
    interactionCanvasDimensions: CanvasDimensions;
    contexts: CanvasContexts;
    chartRuntime: ChartRuntimeInstance | null;
    runtimeLayers: RuntimeLayer[] | null;
    offscreenCanvas: OffscreenCanvas | null;
    offscreenContext: OffscreenCanvasRenderingContext2D | null;
    pendingResizeFrame: number | null;
    resizeObserver: ResizeObserver | null;
    canvasBaseBackground: string | null;
}

interface ChartInteractionState {
    pointer: PointerState;
    crosshair: CrosshairState;
    wheelPayload: import('@features/charts/types.ts').WheelPayload | null;
    wheelPending: boolean;
}

interface ChartState {
    configuration: ChartConfigurationState;
    series: ChartSeriesState;
    viewport: ChartViewportState;
    surface: ChartSurfaceState;
    interaction: ChartInteractionState;
}

type ChartBooleanOption = 'enableCrosshair' | 'enableMagnetMode' | 'enableInertialPanning' | 'enableSmoothZoom' | 'enableXAxisZoom' | 'showAxisCoordinates' | 'showDelta' | 'showLegendTimestamp' | 'autoScale';
const CHART_BOOLEAN_OPTIONS: readonly ChartBooleanOption[] = ['enableCrosshair', 'enableMagnetMode', 'enableInertialPanning', 'enableSmoothZoom', 'enableXAxisZoom', 'showAxisCoordinates', 'showDelta', 'showLegendTimestamp', 'autoScale'];
const CHART_PADDING_SIDES: readonly (keyof ChartPadding)[] = ['top', 'right', 'bottom', 'left'];

const createRenderBuffers = (requestedCapacity: number): RenderBuffers => {
    const capacity = Math.max(8, requestedCapacity);
    return { capacity, x: new Float64Array(capacity), y: new Float64Array(capacity), value: new Float64Array(capacity), valid: new Uint8Array(capacity), index: new Uint32Array(capacity) };
};

const createChartOptions = (element: HTMLElement, input: Partial<ChartOptions>): { options: ChartOptions; padding: ChartPadding; themeColorFlags: ThemeColorFlags; timestampFormatConfig: TimestampFormatConfig } => {
    const defaults: ChartOptions = {
        chartType: 'precision-line',
        colors: { ...DEFAULT_CHART_COLORS },
        autoScale: true,
        scaleType: 'linear',
        valueFormatter: null,
        valuePrecision: null,
        timestampFormat: 'auto',
        enableCrosshair: true,
        enableMagnetMode: false,
        enableInertialPanning: true,
        enableSmoothZoom: true,
        enableXAxisZoom: true,
        showAxisCoordinates: true,
        showDelta: true,
        showLegendTimestamp: true,
        metricName: null,
        statusThresholds: null,
        rightMarginBars: 20,
        maxRightMarginPx: DEFAULT_MAX_RIGHT_MARGIN_PX,
        maxRightMarginRatio: DEFAULT_MAX_RIGHT_MARGIN_RATIO,
        verticalPaddingRatio: DEFAULT_VERTICAL_SCALE_PADDING_RATIO,
        maxDataPoints: DEFAULT_MAX_DATA_POINTS,
        minHeight: DEFAULT_MIN_HEIGHT,
        bottomAxisPadding: DEFAULT_BOTTOM_AXIS_PADDING,
        scaleBounds: null,
        updateThrottleMs: 16,
        zoomEasingMs: 120,
        onRequestHistoricalData: null,
        onZoomChange: null,
        onTimeRangeChange: null,
        chartColorContext: null
    };
    const options: ChartOptions = { ...defaults, ...input };
    for (const key of CHART_BOOLEAN_OPTIONS) options[key] = Boolean(options[key]);
    const resolvedColors = resolvePaletteFromCssAndOverrides(element, input.colors);
    const padding: ChartPadding = { ...DEFAULT_CHART_PADDING };
    if (typeof input.padding === 'number' && Number.isFinite(input.padding) && input.padding >= 0) Object.assign(padding, { top: input.padding, right: input.padding, bottom: input.padding, left: input.padding });
    else if (input.padding) {
        for (const side of CHART_PADDING_SIDES) {
            const value = Number(input.padding[side]);
            if (Number.isFinite(value) && value >= 0) padding[side] = value;
        }
    }
    options.chartType = normalizeChartType(options.chartType);
    options.scaleType = normalizeScaleType(options.scaleType);
    options.rightMarginBars = normalizeClampedInt(options.rightMarginBars, defaults.rightMarginBars, 0);
    options.updateThrottleMs = normalizeClampedInt(options.updateThrottleMs, defaults.updateThrottleMs, 0);
    options.zoomEasingMs = normalizeClampedInt(options.zoomEasingMs, defaults.zoomEasingMs, 60);
    options.maxDataPoints = normalizeClampedInt(options.maxDataPoints, defaults.maxDataPoints, 1, MAX_DATA_POINTS_HARD_LIMIT);
    options.minHeight = normalizeClampedInt(options.minHeight, defaults.minHeight, 40);
    options.maxRightMarginPx = normalizeClampedInt(options.maxRightMarginPx, defaults.maxRightMarginPx, 16);
    options.maxRightMarginRatio = normalizeClampedFloat(options.maxRightMarginRatio, defaults.maxRightMarginRatio, 0.02, 0.45);
    options.verticalPaddingRatio = normalizeClampedFloat(options.verticalPaddingRatio, defaults.verticalPaddingRatio, 0, 0.5);
    options.bottomAxisPadding = normalizeClampedInt(options.bottomAxisPadding, defaults.bottomAxisPadding, 12, 160);
    options.valuePrecision = normalizeValuePrecision(options.valuePrecision);
    options.colors = mergeColorPalette(element, resolvedColors.palette);
    options.padding = { ...padding };
    const yAxisMinRange = 1e-6;
    options.scaleBounds = normalizeScaleBounds({ yAxisMinRange }, options.scaleBounds, options.scaleType);
    return { options, padding, themeColorFlags: sanitizeThemeFlags(resolvedColors.flags), timestampFormatConfig: normalizeTimestampFormat(options.timestampFormat) };
};

const createChartState = (element: HTMLElement, input: Partial<ChartOptions> = {}): ChartState => {
    const configuration = createChartOptions(element, input);
    const capacity = configuration.options.maxDataPoints;
    const dynamicMin = computeDynamicMinZoomLevel(capacity, 10);
    return {
        configuration,
        series: { timestamps: new Float64Array(capacity), values: new Float64Array(capacity), renderBuffers: createRenderBuffers(capacity), dataLength: 0, datasets: [], dataStructure: 'value', sourceSeriesMode: 'value', ohlc: null, heikin: null, heikinDirtyIndex: 0, heikinValidLength: 0, ohlcScratch: { open: null, high: null, low: null, close: null } },
        viewport: {
            visibleRange: { start: 0, end: 0, displayCount: 0, totalSlots: 0, marginSlots: 0, offsetFraction: 0 },
            visibleRangeStats: { min: null, max: null, sum: 0, count: 0 },
            scale: { min: null, max: null, auto: configuration.options.autoScale },
            baseBarPixelWidth: 10,
            zoom: { level: 1, targetLevel: 1, minLevel: dynamicMin, maxLevel: BASE_MAX_ZOOM_LEVEL, isAnimating: false, startTime: 0, startLevel: 1, wheelAccumulator: 0 },
            pan: { offset: 0, velocity: 0, isDragging: false, lastX: 0, lastY: 0, isAtTail: true, startOffset: 0, targetOffset: 0, isZooming: false },
            yAxisMinRange: 1e-6,
            yAxisDrag: { active: false, startY: 0, startMin: 0, startMax: 0, startRange: 0, startCenter: 0, minRange: 1e-6 },
            xAxisDrag: { active: false, startX: 0, startZoomLevel: 1, anchor: 0.5, startPanOffset: 0, startMetrics: { totalSlots: 1, dataSlots: 1, marginSlots: 0 } },
            viewportIntent: null,
            pendingViewportIntent: null,
            suspendIntentRecording: false,
            isHistoricalDataLoading: false,
            lastHistoricalRequestTimestamp: null,
            lastEmittedTimeRange: { start: 0, end: 0, startTs: null, endTs: null }
        },
        surface: { element, canvasLayers: { static: null, data: null, interaction: null }, canvasDimensions: { width: 0, height: 0, dpr: 0 }, interactionCanvasDimensions: { width: 0, height: 0, dpr: 0 }, contexts: { static: null, data: null, interaction: null }, chartRuntime: null, runtimeLayers: null, offscreenCanvas: null, offscreenContext: null, pendingResizeFrame: null, resizeObserver: null, canvasBaseBackground: null },
        interaction: { pointer: { activePointers: new Map(), nativeScrollPointerIds: new Set(), primaryId: null, pinch: null, lastTap: null }, crosshair: { visible: false, x: 0, y: 0, dataIndex: -1, rawIndex: null, value: null, timestamp: null, open: null, high: null, low: null, close: null, datasetValues: null }, wheelPayload: null, wheelPending: false }
    };
};

export { createChartState };
export type { ChartConfigurationState, ChartInteractionState, ChartSeriesState, ChartState, ChartSurfaceState, ChartViewportState };
