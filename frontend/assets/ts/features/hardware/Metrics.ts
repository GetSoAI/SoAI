/* SoAI - Hardware feature metrics [frontend/assets/ts/features/hardware/Metrics.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatPercent } from '@core/primitives/percent.ts';
import { formatPower, formatTemperature } from '@core/localization/public.ts';
import { isFunction } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { DEFAULT_CHART_PADDING, DEFAULT_CHART_TYPE_SEQUENCE, DEFAULT_PRIMARY_BOTTOM_AXIS_PADDING } from '@core/charts/constants.ts';
import { hardwareFormatters } from '@features/hardware/Formatters.ts';

if (!hardwareFormatters || !isFunction(hardwareFormatters.safeNumberFormat)) {
    throw new Error('Hardware metrics require formatters module');
}

type ValueFormatter = (value: number) => string;

const percentFormatter =
    (digits: number = 1): ValueFormatter =>
    (value: number): string =>
        hardwareFormatters.safeNumberFormat(value, (numeric) => formatPercent(numeric, digits));

const temperatureFormatter: ValueFormatter = (value: number): string => hardwareFormatters.safeNumberFormat(value, (numeric) => formatTemperature(numeric, 1));

const powerFormatter: ValueFormatter = (value: number): string => hardwareFormatters.safeNumberFormat(value, (numeric) => formatPower(numeric, 1));

const clockFormatter: ValueFormatter = (value: number): string => hardwareFormatters.safeNumberFormat(value, (numeric) => `${Math.round(numeric)} MHz`);

interface MetricBounds {
    min: number;
    max?: number;
}

interface MetricDefinition {
    realtimeKeyByDevice: Readonly<Record<string, string>>;
    historyKeyByDevice: Readonly<Record<string, string>>;
    label: () => string;
    format: ValueFormatter;
    devices: string[];
    bounds: MetricBounds;
}

type MetricConfigType = Readonly<Record<string, MetricDefinition>>;

const METRIC_CONFIG: MetricConfigType = Object.freeze({
    usage: {
        realtimeKeyByDevice: Object.freeze({
            cpu: 'usage_percent',
            gpu: 'utilization'
        }),
        historyKeyByDevice: Object.freeze({
            cpu: 'usage_percent',
            gpu: 'utilization'
        }),
        label: (): string => i18n.t('hardware.metrics.labels.usage'),
        format: percentFormatter(1),
        devices: ['cpu', 'gpu'],
        bounds: { min: 0, max: 100 }
    },
    memory: {
        realtimeKeyByDevice: Object.freeze({
            cpu: 'memory_percent',
            gpu: 'percent_used'
        }),
        historyKeyByDevice: Object.freeze({
            cpu: 'memory_percent',
            gpu: 'percent_used'
        }),
        label: (): string => i18n.t('hardware.metrics.labels.memory'),
        format: percentFormatter(1),
        devices: ['cpu', 'gpu'],
        bounds: { min: 0, max: 100 }
    },
    temperature: {
        realtimeKeyByDevice: Object.freeze({
            cpu: 'temperature_celsius',
            gpu: 'temperature'
        }),
        historyKeyByDevice: Object.freeze({
            cpu: 'temperature_celsius',
            gpu: 'temperature'
        }),
        label: (): string => i18n.t('hardware.metrics.labels.temperature'),
        format: temperatureFormatter,
        devices: ['cpu', 'gpu'],
        bounds: { min: 0 }
    },
    power: {
        realtimeKeyByDevice: Object.freeze({
            cpu: 'power_draw_watts',
            gpu: 'power_draw_watts'
        }),
        historyKeyByDevice: Object.freeze({
            cpu: 'power_draw_watts',
            gpu: 'power_draw_watts'
        }),
        label: (): string => i18n.t('hardware.metrics.labels.powerDraw'),
        format: powerFormatter,
        devices: ['gpu'],
        bounds: { min: 0 }
    },
    coreClock: {
        realtimeKeyByDevice: Object.freeze({
            gpu: 'core_clock_mhz'
        }),
        historyKeyByDevice: Object.freeze({
            gpu: 'core_clock_mhz'
        }),
        label: (): string => i18n.t('hardware.metrics.labels.coreClock'),
        format: clockFormatter,
        devices: ['gpu'],
        bounds: { min: 0 }
    },
    memClock: {
        realtimeKeyByDevice: Object.freeze({
            gpu: 'mem_clock_mhz'
        }),
        historyKeyByDevice: Object.freeze({
            gpu: 'mem_clock_mhz'
        }),
        label: (): string => i18n.t('hardware.metrics.labels.memoryClock'),
        format: clockFormatter,
        devices: ['gpu'],
        bounds: { min: 0 }
    },
    diskUsage: {
        realtimeKeyByDevice: Object.freeze({
            disk: 'percent_used'
        }),
        historyKeyByDevice: Object.freeze({
            disk: 'percent_used'
        }),
        label: (): string => i18n.t('hardware.metrics.labels.diskUsage'),
        format: percentFormatter(1),
        devices: ['disk'],
        bounds: { min: 0, max: 100 }
    },
    diskUsed: {
        realtimeKeyByDevice: Object.freeze({
            disk: 'used_bytes'
        }),
        historyKeyByDevice: Object.freeze({
            disk: 'used_bytes'
        }),
        label: (): string => i18n.t('hardware.metrics.labels.diskUsed'),
        format: hardwareFormatters.formatBytesValue,
        devices: ['disk'],
        bounds: { min: 0 }
    },
    diskFree: {
        realtimeKeyByDevice: Object.freeze({
            disk: 'free_bytes'
        }),
        historyKeyByDevice: Object.freeze({
            disk: 'free_bytes'
        }),
        label: (): string => i18n.t('hardware.metrics.labels.diskFree'),
        format: hardwareFormatters.formatBytesValue,
        devices: ['disk'],
        bounds: { min: 0 }
    },
    diskTotal: {
        realtimeKeyByDevice: Object.freeze({
            disk: 'total_bytes'
        }),
        historyKeyByDevice: Object.freeze({
            disk: 'total_bytes'
        }),
        label: (): string => i18n.t('hardware.metrics.labels.diskTotal'),
        format: hardwareFormatters.formatBytesValue,
        devices: ['disk'],
        bounds: { min: 0 }
    },
    networkDownload: {
        realtimeKeyByDevice: Object.freeze({
            network: 'download_mbps'
        }),
        historyKeyByDevice: Object.freeze({
            network: 'download_mbps'
        }),
        label: (): string => i18n.t('hardware.metrics.labels.networkDownload'),
        format: hardwareFormatters.formatRateValue,
        devices: ['network'],
        bounds: { min: 0 }
    },
    networkUpload: {
        realtimeKeyByDevice: Object.freeze({
            network: 'upload_mbps'
        }),
        historyKeyByDevice: Object.freeze({
            network: 'upload_mbps'
        }),
        label: (): string => i18n.t('hardware.metrics.labels.networkUpload'),
        format: hardwareFormatters.formatRateValue,
        devices: ['network'],
        bounds: { min: 0 }
    }
});

interface ChartPadding {
    top: number;
    right: number;
    bottom: number;
    left: number;
}

interface ChartDefaults {
    typeSequence: readonly string[];
    primaryPadding: Readonly<ChartPadding>;
    primaryBottomAxisPadding: number;
}

const CHART_DEFAULTS: Readonly<ChartDefaults> = Object.freeze({
    typeSequence: DEFAULT_CHART_TYPE_SEQUENCE,
    primaryPadding: DEFAULT_CHART_PADDING,
    primaryBottomAxisPadding: DEFAULT_PRIMARY_BOTTOM_AXIS_PADDING
});

interface MetricsConfigModule {
    METRIC_CONFIG: MetricConfigType;
    CHART_DEFAULTS: Readonly<ChartDefaults>;
}

const metricsConfig: Readonly<MetricsConfigModule> = Object.freeze({
    METRIC_CONFIG,
    CHART_DEFAULTS
});

export { metricsConfig, METRIC_CONFIG, CHART_DEFAULTS };
export type { MetricDefinition, MetricBounds, MetricConfigType, ChartDefaults, MetricsConfigModule };
