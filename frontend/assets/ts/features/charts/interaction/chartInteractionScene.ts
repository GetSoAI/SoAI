/* SoAI - Chart interaction capability graph [frontend/assets/ts/features/charts/interaction/chartInteractionScene.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartOptions, CrosshairState, Dataset, OhlcValues, PointerState } from '@features/charts/chartTypes.ts';
import type { CanvasLayers, OhlcData, PanState, RedrawRequest, Scale, VisibleRange, XAxisDragState, YAxisDragState } from '@features/charts/component/chartComponentTypes.ts';
import type { ChartEventDetail } from '@features/charts/component/effects.ts';
import type { ChartDimensions, RenderGeometry } from '@features/charts/rendering/renderingModels.ts';
import type { WheelPayload } from '@features/charts/types.ts';
import type { TimeViewportState } from '@features/charts/viewport/timeViewport.ts';

interface ChartInteractionStatePort {
    pointer: PointerState;
    crosshair: CrosshairState;
    wheelPayload: WheelPayload | null;
    wheelPending: boolean;
    yAxisDrag: YAxisDragState;
    xAxisDrag: XAxisDragState;
}

interface ChartInteractionViewportStatePort {
    time: TimeViewportState;
    pan: PanState;
    scale: Scale;
    visibleRange: VisibleRange;
    yAxisMinRange: number;
}

interface ChartInteractionSurfacePort {
    element: HTMLElement;
    canvasLayers: CanvasLayers;
    resize(): void;
}

interface ChartInteractionViewportCommands {
    getChartDimensions(): ChartDimensions;
    panByPixels(deltaPx: number): boolean;
    zoomBy(anchorX: number, factor: number, animate: boolean): boolean;
    zoomTo(anchorX: number, msPerPx: number): boolean;
    enforceScaleBounds(): void;
    panVertical(deltaY: number): boolean;
    setAutoScale(enabled: boolean): void;
    resetZoom(): void;
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
    renderGeometry(dimensions?: ChartDimensions): RenderGeometry | null;
    valueViewport(): { height: number; top: number } | null;
}

interface ChartInteractionPresentationPort {
    valueToPixel(value: number, height: number, top: number): number;
}

interface ChartInteractionEffectsPort {
    requestRedraw(requirements?: RedrawRequest): void;
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
