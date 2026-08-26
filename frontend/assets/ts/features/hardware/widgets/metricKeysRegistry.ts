/* SoAI - Hardware feature metric keys registry [frontend/assets/ts/features/hardware/widgets/metricKeysRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface MetricKeySet {
    readonly utilization: readonly string[];
    readonly memory: readonly string[];
    readonly power: readonly string[];
    readonly temperature: readonly string[];
    readonly powerLimit: readonly string[];
}

const CPU_METRIC_KEYS: Readonly<MetricKeySet> = Object.freeze({
    utilization: Object.freeze(['usage_percent']),
    memory: Object.freeze(['memory_percent']),
    power: Object.freeze(['power_draw_watts']),
    temperature: Object.freeze(['temperature_celsius']),
    powerLimit: Object.freeze(['power_limit_watts'])
});

const GPU_METRIC_KEYS: Readonly<MetricKeySet> = Object.freeze({
    utilization: Object.freeze(['utilization']),
    memory: Object.freeze(['percent_used']),
    power: Object.freeze(['power_draw_watts']),
    temperature: Object.freeze(['temperature']),
    powerLimit: Object.freeze(['power_limit_watts'])
});

export { CPU_METRIC_KEYS, GPU_METRIC_KEYS };
export type { MetricKeySet };
