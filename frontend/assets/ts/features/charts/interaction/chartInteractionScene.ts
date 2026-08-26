/* SoAI - Chart interaction capability graph [frontend/assets/ts/features/charts/interaction/chartInteractionScene.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ChartOptions, CrosshairState, Dataset, OhlcValues, PointerState } from '@features/charts/chartTypes.ts';
import type { CanvasLayers, OhlcData, PanState, RedrawRequest, Scale, SlotMetrics, XAxisDragState, YAxisDragState, ZoomState } from '@features/charts/component/chartComponentTypes.ts';
import type { ChartEventDetail } from '@features/charts/component/effects.ts';
import type { ChartDimensions, RenderGeometry } from '@features/charts/rendering/renderingModels.ts';
import type { WheelPayload } from '@features/charts/types.ts';

interface ChartInteractionStatePort {
    pointer: PointerState;
    crosshair: CrosshairState;
    wheelPayload: WheelPayload | null;
    wheelPending: boolean;
    yAxisDrag: YAxisDragState;
    xAxisDrag: XAxisDragState;
}

interface ChartInteractionViewportStatePort {
    zoom: ZoomState;
    pan: PanState;
    scale: Scale;
    visibleRange: { start: number; end: number; displayCount: number; offsetFraction: number };
    yAxisMinRange: number;
}

interface ChartInteractionSurfacePort {
    element: HTMLElement;
    canvasLayers: CanvasLayers;
    resize(): void;
}

interface ChartInteractionViewportCommands {
    getChartDimensions(): ChartDimensions;
    getPixelsPerBar(): number;
    getSlotMetrics(): SlotMetrics;
    getSlotMetricsForLevel(level: number | null | undefined): SlotMetrics;
    getMaxOffsetForMetrics(metrics?: SlotMetrics | null): number;
    clampPanOffset(): void;
    enforceScaleBounds(): void;
    panVertical(deltaY: number): boolean;
    markManual(source?: string): void;
    setAutoScale(enabled: JsonValue | null | undefined): void;
    resetZoom(options?: { alignToTail?: boolean }): void;
    alignToLatest(): void;
}

interface ChartInteractionDataPort {
    dataLength: number;
    datasets: Dataset[];
    timestamps: Float64Array;
    ohlcScratch: OhlcValues;
    findFirstTimestamp(timestamp: number): number;
    findLastTimestamp(timestamp: number): number;
    closeValue(index: number): number | undefined;
    ohlcAt(index: number, target?: OhlcValues | null): OhlcValues;
    renderableOhlc(): OhlcData | null;
    hasOhlc(): boolean;
    isOhlcType(type?: string): boolean;
    interpolate(rawIndex: number, start: number, end: number): { value: number | null; timestamp: number | null };
}

interface ChartInteractionGeometryPort {
    renderGeometry(dimensions?: ChartDimensions): RenderGeometry;
    valueViewport(): { height: number; top: number } | null;
    xForVisibleIndex(index: number): number;
}

interface ChartInteractionPresentationPort {
    valueToPixel(value: number, height: number, top: number): number;
}

interface ChartInteractionEffectsPort {
    requestRedraw(requirements?: RedrawRequest): void;
    scheduleFrame(): void;
    emit(event: string, detail?: ChartEventDetail): void;
}

interface ChartInteractionScene {
    configuration: { options: ChartOptions };
    interaction: ChartInteractionStatePort;
    viewportState: ChartInteractionViewportStatePort;
    surface: ChartInteractionSurfacePort;
    viewport: ChartInteractionViewportCommands;
    data: ChartInteractionDataPort;
    geometry: ChartInteractionGeometryPort;
    presentation: ChartInteractionPresentationPort;
    effects: ChartInteractionEffectsPort;
}

export type { ChartInteractionDataPort, ChartInteractionEffectsPort, ChartInteractionGeometryPort, ChartInteractionPresentationPort, ChartInteractionScene, ChartInteractionStatePort, ChartInteractionSurfacePort, ChartInteractionViewportCommands, ChartInteractionViewportStatePort };
