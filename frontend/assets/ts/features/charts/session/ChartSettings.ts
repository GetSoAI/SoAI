/* SoAI - Chart settings ownership [frontend/assets/ts/features/charts/session/ChartSettings.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { DEFAULT_MAX_RIGHT_MARGIN_PX, DEFAULT_MAX_RIGHT_MARGIN_RATIO, INTERACTION_BOOLEAN_OPTIONS, MAX_DATA_POINTS_HARD_LIMIT, dateTimeFormatterCache } from '@features/charts/component/chartComponentStatics.ts';
import { normalizeTimestampFormat } from '@features/charts/component/data/timeFormatting.ts';
import { normalizeChartType, normalizeClampedFloat, normalizeClampedInt, normalizeScaleBounds, normalizeScaleType, normalizeValuePrecision } from '@features/charts/component/state/actions.ts';
import { deriveThemeFlags, mergeColorPalette, separatePaletteMetadata } from '@features/charts/component/state/service.ts';
import type { ChartColorContext, ChartOptionValue, ChartOptions, ChartOptionsRecord, ChartPaddingInput, ChartPaddingOptions, ChartScaleBounds, ChartThemeManagedPaletteInput, ChartTimestampFormatInput, ChartTimestampFormatOptionInput, ChartTimestampFormatter, ChartValueFormatter } from '@features/charts/chartTypes.ts';
import type { ChartConfigurationState } from '@features/charts/session/chartState.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import type { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';

interface ChartSettingsSeriesPort {
    applyChartType(type: string): void;
    resizeCapacity(capacity: number): void;
}

interface ChartSettingsViewportPort {
    readonly yAxisMinRange: number;
    setAutoScale(enabled: boolean): void;
    enforceScaleBounds(): void;
    recalculateZoomBounds(): void;
    clampPanOffset(): void;
}

interface ChartSettingsSurfacePort {
    readonly element: HTMLElement;
    applyBackground(): void;
    applyMinimumHeight(): void;
    syncInteractionBounds(): void;
}

interface ChartSettingsDependencies {
    configuration: ChartConfigurationState;
    series: ChartSettingsSeriesPort;
    viewport: ChartSettingsViewportPort;
    redraw: ChartRedrawQueue;
    surface: ChartSettingsSurfacePort;
}

const isObjectOption = (value: ChartOptionValue): value is Record<string, ChartOptionValue | undefined> => isObject(value);
const isThemePalette = (value: ChartOptionValue): value is ChartThemeManagedPaletteInput => isObject(value);
const isChartPadding = (value: ChartOptionValue): value is ChartPaddingInput => typeof value === 'number' || isObject(value);
const isChartScaleBounds = (value: ChartOptionValue): value is ChartScaleBounds => isObject(value);
const isChartTimestampFormatter = (value: ChartOptionValue): value is ChartTimestampFormatter => typeof value === 'function';
const isChartTimestampFormatOption = (value: ChartOptionValue): value is ChartTimestampFormatOptionInput => isObject(value);
const isChartTimestampFormat = (value: ChartOptionValue): value is ChartTimestampFormatInput => isString(value) || isChartTimestampFormatter(value) || isChartTimestampFormatOption(value);
const isChartValueFormatter = (value: ChartOptionValue): value is ChartValueFormatter => typeof value === 'function';
const isHistoricalDataRequest = (value: ChartOptionValue): value is NonNullable<ChartOptions['onRequestHistoricalData']> => typeof value === 'function';
const isZoomChangeHandler = (value: ChartOptionValue): value is NonNullable<ChartOptions['onZoomChange']> => typeof value === 'function';
const isTimeRangeChangeHandler = (value: ChartOptionValue): value is NonNullable<ChartOptions['onTimeRangeChange']> => typeof value === 'function';
const isChartColorContext = (value: ChartOptionValue): value is ChartColorContext => isObject(value);
const CHART_PADDING_SIDES: readonly (keyof ChartPaddingOptions)[] = ['top', 'right', 'bottom', 'left'];

class ChartSettings {
    readonly #configuration: ChartConfigurationState;
    readonly #series: ChartSettingsSeriesPort;
    readonly #viewport: ChartSettingsViewportPort;
    readonly #redraw: ChartRedrawQueue;
    readonly #surface: ChartSettingsSurfacePort;

    constructor({ configuration, series, viewport, redraw, surface }: ChartSettingsDependencies) {
        this.#configuration = configuration;
        this.#series = series;
        this.#viewport = viewport;
        this.#redraw = redraw;
        this.#surface = surface;
    }

    get snapshot(): Readonly<ChartOptions> {
        const options = this.#configuration.options;
        return Object.freeze({ ...options, colors: Object.freeze({ ...options.colors }), padding: options.padding ? Object.freeze({ ...options.padding }) : undefined, scaleBounds: options.scaleBounds ? Object.freeze({ ...options.scaleBounds }) : null });
    }

    update(options: ChartOptionsRecord | null): void {
        if (!isObject(options)) throw new TypeError('Chart settings update requires an options object');
        for (const [key, value] of Object.entries(options)) this.#updateOption(key, value);
    }

    setChartType(type: string): void {
        this.#updateChartType(type);
    }

    setMetricName(name: string | null): void {
        this.#configuration.options.metricName = (isString(name) ? name.trim() : '') || null;
        this.#redraw.request({ interaction: true });
    }

    setValueFormatter(formatter: ChartValueFormatter): void {
        this.#configuration.options.valueFormatter = formatter;
        this.#redraw.request({ static: true, data: true, interaction: true });
    }

    #updateOption(key: string, value: ChartOptionValue): void {
        if (INTERACTION_BOOLEAN_OPTIONS.has(key)) {
            this.#configuration.options[key] = Boolean(value);
            this.#redraw.request({ interaction: true });
            return;
        }
        switch (key) {
            case 'chartType':
                this.#updateChartType(isString(value) ? value : null);
                return;
            case 'maxDataPoints':
                this.#updateCapacity(isString(value) || typeof value === 'number' ? value : null);
                return;
            case 'colors':
                this.#updateColors(isThemePalette(value) ? value : null);
                return;
            case 'valueFormatter':
                this.#configuration.options.valueFormatter = isChartValueFormatter(value) ? value : null;
                this.#redraw.request({ static: true, data: true, interaction: true });
                return;
            case 'valuePrecision':
                this.#configuration.options.valuePrecision = normalizeValuePrecision(isString(value) || typeof value === 'number' ? value : null);
                this.#redraw.request({ static: true, data: true, interaction: true });
                return;
            case 'metricName':
                this.setMetricName(isString(value) ? value : null);
                return;
            case 'statusThresholds':
                this.#updateStatusThresholds(isObjectOption(value) ? value : null);
                return;
            case 'autoScale': {
                const enabled = Boolean(value);
                this.#configuration.options.autoScale = enabled;
                this.#viewport.setAutoScale(enabled);
                if (!enabled) this.#viewport.enforceScaleBounds();
                this.#redraw.request({ data: true, interaction: true });
                return;
            }
            case 'scaleType':
                this.#configuration.options.scaleType = normalizeScaleType(isString(value) ? value : null);
                this.#redraw.request({ data: true, interaction: true });
                return;
            case 'padding':
                this.#updatePadding(isChartPadding(value) ? value : null);
                return;
            case 'minHeight':
                this.#configuration.options.minHeight = normalizeClampedInt(isString(value) || typeof value === 'number' ? value : null, this.#configuration.options.minHeight, 40);
                this.#surface.applyMinimumHeight();
                this.#redraw.request({ static: true, data: true, interaction: true });
                return;
            case 'bottomAxisPadding':
                this.#configuration.options.bottomAxisPadding = normalizeClampedInt(isString(value) || typeof value === 'number' ? value : null, this.#configuration.options.bottomAxisPadding, 12, 160);
                this.#surface.syncInteractionBounds();
                this.#redraw.request({ static: true, data: true, interaction: true });
                return;
            case 'verticalPaddingRatio':
                this.#configuration.options.verticalPaddingRatio = normalizeClampedFloat(isString(value) || typeof value === 'number' ? value : null, this.#configuration.options.verticalPaddingRatio, 0, 0.5);
                this.#redraw.request({ static: this.#configuration.options.autoScale, data: true, interaction: true });
                return;
            case 'scaleBounds':
                this.#configuration.options.scaleBounds = normalizeScaleBounds({ yAxisMinRange: this.#viewport.yAxisMinRange }, isChartScaleBounds(value) ? value : null, this.#configuration.options.scaleType);
                if (this.#configuration.options.scaleBounds) this.#viewport.enforceScaleBounds();
                this.#redraw.request({ data: true, interaction: true });
                return;
            case 'timestampFormat':
                this.#updateTimestampFormat(isChartTimestampFormat(value) ? value : null);
                return;
            case 'updateThrottleMs': {
                const delay = normalizeClampedInt(isString(value) || typeof value === 'number' ? value : null, this.#configuration.options.updateThrottleMs, 0);
                this.#configuration.options.updateThrottleMs = delay;
                return;
            }
            case 'zoomEasingMs':
                this.#configuration.options.zoomEasingMs = normalizeClampedInt(isString(value) || typeof value === 'number' ? value : null, this.#configuration.options.zoomEasingMs, 60);
                return;
            case 'onRequestHistoricalData':
                this.#configuration.options.onRequestHistoricalData = isHistoricalDataRequest(value) ? value : null;
                return;
            case 'onZoomChange':
                this.#configuration.options.onZoomChange = isZoomChangeHandler(value) ? value : null;
                return;
            case 'onTimeRangeChange':
                this.#configuration.options.onTimeRangeChange = isTimeRangeChangeHandler(value) ? value : null;
                return;
            case 'chartColorContext':
                this.#configuration.options.chartColorContext = isChartColorContext(value) ? value : null;
                this.#redraw.request({ static: true, data: true, interaction: true });
                return;
            case 'rightMarginBars':
            case 'maxRightMarginPx':
            case 'maxRightMarginRatio':
                this.#updateMargin(key, isString(value) || typeof value === 'number' ? value : null);
                return;
            default:
                throw new Error(`Unsupported chart option: ${key}`);
        }
    }

    #updateChartType(value: string | null): void {
        const type = normalizeChartType(value);
        if (type === this.#configuration.options.chartType) return;
        this.#series.applyChartType(type);
        this.#configuration.options.chartType = type;
        this.#redraw.request({ data: true, interaction: true });
    }

    #updateCapacity(value: number | string | null): void {
        const capacity = normalizeClampedInt(value, this.#configuration.options.maxDataPoints, 1, MAX_DATA_POINTS_HARD_LIMIT);
        if (capacity === this.#configuration.options.maxDataPoints) return;
        this.#series.resizeCapacity(capacity);
        this.#configuration.options.maxDataPoints = capacity;
        this.#viewport.recalculateZoomBounds();
        this.#viewport.clampPanOffset();
        this.#redraw.request({ static: true, data: true, interaction: true });
    }

    #updateColors(value: ChartThemeManagedPaletteInput | null): void {
        if (!isObject(value)) return;
        const { palette, meta } = separatePaletteMetadata(value);
        const colors = mergeColorPalette(this.#surface.element, palette);
        if (JSON.stringify(colors) === JSON.stringify(this.#configuration.options.colors)) return;
        this.#configuration.options.colors = colors;
        this.#configuration.themeColorFlags = deriveThemeFlags(this.#configuration.themeColorFlags, meta, palette);
        this.#surface.applyBackground();
        this.#redraw.request({ static: true, data: true, interaction: true });
    }

    #updateStatusThresholds(value: Record<string, ChartOptionValue | undefined> | null): void {
        const thresholds: { red?: number; yellow?: number } = {};
        if (typeof value?.['red'] === 'number' && Number.isFinite(value['red'])) thresholds.red = value['red'];
        if (typeof value?.['yellow'] === 'number' && Number.isFinite(value['yellow'])) thresholds.yellow = value['yellow'];
        this.#configuration.options.statusThresholds = Object.keys(thresholds).length > 0 ? thresholds : null;
        this.#redraw.request({ interaction: true });
    }

    #updatePadding(value: ChartPaddingInput): void {
        if (!isObject(value) && typeof value !== 'number') return;
        for (const side of CHART_PADDING_SIDES) {
            const candidate = typeof value === 'number' ? value : Number(value[side]);
            if (Number.isFinite(candidate) && candidate >= 0) this.#configuration.padding[side] = candidate;
        }
        this.#configuration.options.padding = { ...this.#configuration.padding };
        this.#surface.syncInteractionBounds();
        this.#redraw.request({ static: true, data: true, interaction: true });
    }

    #updateTimestampFormat(value: ChartTimestampFormatInput): void {
        const normalized = normalizeTimestampFormat(value);
        const previous = this.#configuration.timestampFormatConfig;
        if (previous.mode === normalized.mode && previous.formatter === normalized.formatter && previous.timeZone === normalized.timeZone) return;
        this.#configuration.timestampFormatConfig = normalized;
        this.#configuration.options.timestampFormat = value ?? normalized;
        dateTimeFormatterCache.clear();
        this.#redraw.request({ static: true, data: true, interaction: true });
    }

    #updateMargin(key: 'rightMarginBars' | 'maxRightMarginPx' | 'maxRightMarginRatio', value: number | string | null): void {
        const ratio = key === 'maxRightMarginRatio';
        const fallback = ratio ? DEFAULT_MAX_RIGHT_MARGIN_RATIO : key === 'rightMarginBars' ? 20 : DEFAULT_MAX_RIGHT_MARGIN_PX;
        this.#configuration.options[key] = ratio ? normalizeClampedFloat(value, fallback, 0.02, 0.45) : normalizeClampedInt(value, fallback, key === 'rightMarginBars' ? 0 : 16);
        this.#viewport.clampPanOffset();
        this.#redraw.request({ data: true, interaction: true });
    }
}

export { ChartSettings };
export type { ChartSettingsDependencies, ChartSettingsSeriesPort, ChartSettingsSurfacePort, ChartSettingsViewportPort };
