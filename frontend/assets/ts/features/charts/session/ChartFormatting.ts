/* SoAI - Chart value and time formatting ownership [frontend/assets/ts/features/charts/session/ChartFormatting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ChartOptions, ChartTimestampFormatter, TimestampFormatConfig } from '@features/charts/chartTypes.ts';
import { formatValue, valueToPixel } from '@features/charts/component/data/visibleRange.ts';
import { formatAxisTimestamp, formatDateTime, formatDetailedTimestamp, formatTimestamp, getVisibleTimeSpan, getVisibleTimeWindow, resolveAxisFormat } from '@features/charts/component/data/timeFormatting.ts';
import type { Scale, VisibleRange } from '@features/charts/component/chartComponentTypes.ts';
import type { ChartViewportSeriesPort } from '@features/charts/session/ChartViewport.ts';
import type { ChartConfigurationState, ChartViewportState } from '@features/charts/session/chartState.ts';
import type { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';
import type { AxisCache } from '@features/charts/rendering/renderingModels.ts';

class ChartFormatting {
    readonly #configuration: ChartConfigurationState;
    readonly #series: ChartViewportSeriesPort;
    readonly #viewport: ChartViewportState;
    readonly #redraw: ChartRedrawQueue;

    constructor(configuration: ChartConfigurationState, series: ChartViewportSeriesPort, viewport: ChartViewportState, redraw: ChartRedrawQueue) {
        this.#configuration = configuration;
        this.#series = series;
        this.#viewport = viewport;
        this.#redraw = redraw;
    }

    valueToPixel(value: number, height: number, top: number): number {
        return valueToPixel(this, value, height, top);
    }
    formatValue(value: number): string {
        return formatValue(this, value);
    }
    formatTimestamp(timestamp: number, mode: ChartTimestampFormatter | string | null = 'auto'): string {
        return formatTimestamp(this, timestamp, mode);
    }
    formatAxisTimestamp(timestamp: number, span?: number): string {
        return formatAxisTimestamp(this, timestamp, span);
    }
    formatDetailedTimestamp(timestamp: number, options: JsonObject | null = null): string {
        return formatDetailedTimestamp(this, timestamp, options);
    }
    formatDateTime(timestamp: number, options: Intl.DateTimeFormatOptions | Record<string, JsonValue | null | undefined> = {}): string {
        return formatDateTime(this, timestamp, options);
    }
    resolveAxisFormat(span: number): { options: Intl.DateTimeFormatOptions } {
        return resolveAxisFormat(span);
    }
    getVisibleTimeWindow(): { startTs: number; endTs: number; span: number } | null {
        return getVisibleTimeWindow(this);
    }
    getVisibleTimeSpan(): number {
        return getVisibleTimeSpan(this);
    }

    get chartOptions(): ChartOptions {
        return this.#configuration.options;
    }
    get timestampFormatConfig(): TimestampFormatConfig {
        return this.#configuration.timestampFormatConfig;
    }
    get visibleRange(): VisibleRange {
        return this.#viewport.visibleRange;
    }
    get timestamps(): Float64Array {
        return this.#series.timestamps;
    }
    get dataLength(): number {
        return this.#series.dataLength;
    }
    get scale(): Scale {
        return this.#viewport.scale;
    }
    get axisCache(): AxisCache | null {
        return this.#redraw.axis;
    }
}

export { ChartFormatting };
