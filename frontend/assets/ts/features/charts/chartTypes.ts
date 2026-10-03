/* SoAI - Charts feature chart types [frontend/assets/ts/features/charts/chartTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ComponentOptionValue } from '@core/BaseComponent.ts';

export interface ChartColorComponentInput {
    r?: number | undefined;
    g?: number | undefined;
    b?: number | undefined;
    a?: number | undefined;
}

export interface PointerState {
    activePointers: Map<number, { clientX: number; clientY: number; id?: number; type?: string; x?: number; y?: number }>;
    nativeScrollPointerIds: Set<number>;
    primaryId: number | null;
    pinch: {
        lastDistance: number;
        lastCenterX: number;
    } | null;
    lastTap: {
        time: number;
        x: number;
        y: number;
    } | null;
    hoverX: number | null;
}

export interface CrosshairState {
    visible: boolean;
    x: number;
    y: number;
    dataIndex: number;
    rawIndex: number | null;
    value: number | null;
    timestamp: number | null;
    open: number | null;
    high: number | null;
    low: number | null;
    close: number | null;
    datasetValues: Record<string, number> | null;
    gap: boolean;
}

export interface OhlcValues {
    open: number | null;
    high: number | null;
    low: number | null;
    close: number | null;
}

export interface VisiblePointsCache {
    series: Float64Array | number[];
    start: number;
    end: number;
    dataLength: number;
    scaleMin: number | null;
    scaleMax: number | null;
    chartHeight: number;
    chartTop: number;
    plotLeft: number;
    plotWidth: number;
    rightEdgeTs: number;
    msPerPx: number;
    x?: Float64Array | undefined;
    y?: Float64Array | undefined;
    value?: Float64Array | undefined;
    valid?: Uint8Array | undefined;
    index?: Uint32Array | undefined;
    length: number;
}

export interface ColorPalette {
    primary?: string | null | undefined;
    secondary?: string | null | undefined;
    tertiary?: string | null | undefined;
    quaternary?: string | null | undefined;
    grid?: string | null | undefined;
    crosshair?: string | null | undefined;
    text?: string | null | undefined;
    textSecondary?: string | null | undefined;
    statusGreen?: string | null | undefined;
    statusYellow?: string | null | undefined;
    statusRed?: string | null | undefined;
    background?: string | null | undefined;
    [key: string]: string | null | undefined;
}

export interface ThemeStyles {
    isDark?: boolean | undefined;
    background?: string | undefined;
    plotBackground?: string | undefined;
    legendBackground?: string | undefined;
    legendTextColor?: string | null | undefined;
    legendBorderColor?: string | undefined;
    crosshairValueBackground: string;
    crosshairValueTextColor: string;
    axisGuideColor?: string | undefined;
    candlestickUpColor?: string | undefined;
    candlestickDownColor?: string | undefined;
}

export interface ChartTimestampFormatOptionInput {
    format?: ChartTimestampFormatter | undefined;
    formatter?: ChartTimestampFormatter | null | undefined;
    mode?: string | undefined;
    timeZone?: string | null | undefined;
}

export interface ChartThemeFlagInput {
    primary?: boolean | undefined;
    secondary?: boolean | undefined;
    tertiary?: boolean | undefined;
    quaternary?: boolean | undefined;
    grid?: boolean | undefined;
    crosshair?: boolean | undefined;
    text?: boolean | undefined;
    textSecondary?: boolean | undefined;
    statusGreen?: boolean | undefined;
    statusYellow?: boolean | undefined;
    statusRed?: boolean | undefined;
    background?: boolean | undefined;
}

export interface ChartThemeManagedPaletteInput {
    __themeManaged?: ChartThemeFlagInput | string | null | undefined;
    primary?: string | null | undefined;
    secondary?: string | null | undefined;
    tertiary?: string | null | undefined;
    quaternary?: string | null | undefined;
    grid?: string | null | undefined;
    crosshair?: string | null | undefined;
    text?: string | null | undefined;
    textSecondary?: string | null | undefined;
    statusGreen?: string | null | undefined;
    statusYellow?: string | null | undefined;
    statusRed?: string | null | undefined;
    background?: string | null | undefined;
}

export interface ChartTimestampChartReference {
    timestampFormatConfig?: TimestampFormatConfig | undefined;
    visibleRange?: { startTs: number; endTs: number } | undefined;
    dataLength?: number | undefined;
    timestamps?: Float64Array | undefined;
    formatDateTime?: ((timestamp: number, base?: Intl.DateTimeFormatOptions) => string) | undefined;
    resolveAxisFormat?: ((spanMs: number) => { options: Intl.DateTimeFormatOptions }) | undefined;
}

export interface ChartTimestampContext {
    context: string;
    chart?: ChartTimestampChartReference | undefined;
    spanMs?: number | undefined;
    includeSeconds?: boolean | undefined;
    includeMilliseconds?: boolean | undefined;
}

export type ChartTimestampFormatter = (ts: number, context: ChartTimestampContext | null | undefined) => string;
export type ChartTimestampFormatInput = ChartTimestampFormatter | ChartTimestampFormatOptionInput | string | null | undefined;
export type ChartColorInput = string | ChartColorComponentInput | null | undefined;
export type ChartPaddingInput = ChartPaddingOptions | number | null | undefined;

export interface TimestampFormatConfig {
    mode: string;
    formatter: ChartTimestampFormatter | null;
    timeZone: string | null;
}

export interface ChartColorContext {
    device?: string | undefined;
    deviceIndex?: number | undefined;
    metric?: string | undefined;
    metricIndex?: number | undefined;
    subjectName?: string | undefined;
}

export type ChartStatusThresholds = { red?: number | undefined; yellow?: number | undefined };
export type ChartScaleBounds = { min?: number | undefined; max?: number | undefined };
export type ChartPaddingOptions = { top: number; right: number; bottom: number; left: number };
export type ChartValueFormatter = (value: number) => string;
export type ChartHistoryStatus = 'idle' | 'loading' | 'failed' | 'exhausted' | 'capped';

export interface ChartHistoryPort {
    readonly status: ChartHistoryStatus;
    readonly oldestNavigableTs: number | null;
    demand(visibleStartTs: number, visibleEndTs: number): void;
    retry(): void;
}

export type ChartOptionValue = ComponentOptionValue | ColorPalette | ChartThemeManagedPaletteInput | TimestampFormatConfig | ChartTimestampFormatOptionInput | ChartColorContext | ChartStatusThresholds | ChartScaleBounds | ChartPaddingOptions | ChartTimestampFormatter | ChartValueFormatter | ChartHistoryPort | CallableFunction | ((startTs: number, endTs: number) => void) | Float64Array | number[] | null | undefined;
export type ChartOptionsRecord = Record<string, ChartOptionValue>;

export interface ChartOptions {
    chartType: string;
    colors: ColorPalette;
    autoScale: boolean;
    scaleType: string;
    valueFormatter: ChartValueFormatter | null;
    valuePrecision: number | null;
    timestampFormat: string | ChartTimestampFormatter | TimestampFormatConfig | ChartTimestampFormatOptionInput;
    enableCrosshair: boolean;
    enableMagnetMode: boolean;
    enableSmoothZoom: boolean;
    enableXAxisZoom: boolean;
    showAxisCoordinates: boolean;
    showDelta: boolean;
    showLegendTimestamp: boolean;
    metricName: string | null;
    statusThresholds: ChartStatusThresholds | null;
    verticalPaddingRatio: number;
    expectedSampleIntervalMs: number;
    maxDataPoints: number;
    minHeight: number;
    bottomAxisPadding: number;
    scaleBounds: ChartScaleBounds | null;
    updateThrottleMs: number;
    zoomEasingMs: number;
    history: ChartHistoryPort | null;
    onTimeRangeChange: ((startTs: number, endTs: number) => void) | null;
    chartColorContext: ChartColorContext | null;
    padding?: ChartPaddingOptions | undefined;
    [key: string]: ChartOptionValue;
}

export type DatasetValue = Float64Array | readonly number[] | null | undefined;

export interface Dataset {
    name?: string | undefined;
    values?: Float64Array | number[] | undefined;
    color?: string | undefined;
    showEndpointMarker?: boolean | undefined;
    markerColor?: string | undefined;
}

export type DatasetInput = Omit<Dataset, 'values'> & { values?: DatasetValue };
