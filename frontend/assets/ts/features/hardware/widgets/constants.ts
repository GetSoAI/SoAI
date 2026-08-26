/* SoAI - Hardware feature widgets constants [frontend/assets/ts/features/hardware/widgets/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { TEMPERATURE_CRITICAL_CELSIUS, TEMPERATURE_MAX_SCALE_CELSIUS, TEMPERATURE_WARNING_CELSIUS } from '@features/hardware/thermalSeverity.ts';
import { minutesToMs } from '@core/time/durations.ts';

interface WidgetSize {
    WIDTH: number;
    HEIGHT: number;
}

interface ScaleConfigEntry {
    points: number;
    durationMs: number;
}

interface MetricConfig {
    colorVar: string;
}

interface GpuMetrics {
    core: MetricConfig;
    vram: MetricConfig;
    power: MetricConfig;
    temperature: MetricConfig;
}

interface CpuMetrics {
    core: MetricConfig;
    ram: MetricConfig;
    power: MetricConfig;
    temperature: MetricConfig;
}

interface NetworkMetrics {
    download: MetricConfig;
    upload: MetricConfig;
}

interface WidgetConstantsType {
    DEFAULT_SIZE: Readonly<WidgetSize>;
    SCALE_CONFIG: Readonly<Record<string, Readonly<ScaleConfigEntry>>>;
    GPU_METRICS: Readonly<GpuMetrics>;
    CPU_METRICS: Readonly<CpuMetrics>;
    NETWORK_METRICS: Readonly<NetworkMetrics>;
    TEMPERATURE_WARNING_THRESHOLD: number;
    TEMPERATURE_THRESHOLD: number;
    TEMPERATURE_MAX_SCALE: number;
    SVG_VIEWBOX: number;
}

const WIDGET_SIZE: Readonly<WidgetSize> = Object.freeze({
    WIDTH: 300,
    HEIGHT: 300
});

const WIDGET_HISTORY_REQUEST_PADDING_MS = 30_000;

const SCALE_CONFIG: Readonly<Record<string, Readonly<ScaleConfigEntry>>> = Object.freeze({
    '5m': Object.freeze({ points: 200, durationMs: minutesToMs(5) })
});

const GPU_METRICS: Readonly<GpuMetrics> = Object.freeze({
    core: Object.freeze({ colorVar: '--hardware-widget-metric-core' }),
    vram: Object.freeze({ colorVar: '--hardware-widget-metric-vram' }),
    power: Object.freeze({ colorVar: '--hardware-widget-metric-power' }),
    temperature: Object.freeze({ colorVar: '--hardware-widget-metric-temperature' })
});

const CPU_METRICS: Readonly<CpuMetrics> = Object.freeze({
    core: Object.freeze({ colorVar: '--hardware-widget-metric-core' }),
    ram: Object.freeze({ colorVar: '--hardware-widget-metric-ram' }),
    power: Object.freeze({ colorVar: '--hardware-widget-metric-power' }),
    temperature: Object.freeze({ colorVar: '--hardware-widget-metric-temperature' })
});

const NETWORK_METRICS: Readonly<NetworkMetrics> = Object.freeze({
    download: Object.freeze({ colorVar: '--hardware-widget-metric-network-download' }),
    upload: Object.freeze({ colorVar: '--hardware-widget-metric-network-upload' })
});

const WIDGET_CONSTANTS: Readonly<WidgetConstantsType> = Object.freeze({
    DEFAULT_SIZE: WIDGET_SIZE,
    SCALE_CONFIG,
    GPU_METRICS,
    CPU_METRICS,
    NETWORK_METRICS,
    TEMPERATURE_WARNING_THRESHOLD: TEMPERATURE_WARNING_CELSIUS,
    TEMPERATURE_THRESHOLD: TEMPERATURE_CRITICAL_CELSIUS,
    TEMPERATURE_MAX_SCALE: TEMPERATURE_MAX_SCALE_CELSIUS,
    SVG_VIEWBOX: 250
});

export { WIDGET_CONSTANTS, WIDGET_SIZE, SCALE_CONFIG, GPU_METRICS, CPU_METRICS, NETWORK_METRICS, WIDGET_HISTORY_REQUEST_PADDING_MS };
export type { WidgetSize, ScaleConfigEntry, MetricConfig, GpuMetrics, CpuMetrics, NetworkMetrics, WidgetConstantsType };
