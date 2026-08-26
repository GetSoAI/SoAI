/* SoAI - Hardware feature GPU widget [frontend/assets/ts/features/hardware/widgets/GPUWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { BaseHardwareWidget } from '@features/hardware/widgets/BaseHardwareWidget.ts';
import type { HardwareWidgetDataPoint, HardwareWidgetHistoryData, WidgetConfig, WidgetOptions } from '@features/hardware/widgets/contracts.ts';
import { GPU_METRICS } from '@features/hardware/widgets/constants.ts';
import type { GPUDeviceData } from '@features/hardware/widgets/internalContracts.ts';
import { GPU_METRIC_KEYS } from '@features/hardware/widgets/metricKeysRegistry.ts';
import { resolveHardwareDeviceDisplayName } from '@features/hardware/deviceNames.ts';
import { createStandardWidgetDataPoint, hasStandardPowerMetric, hasStandardTemperatureMetric, normalizeStandardWidgetData, transformStandardWidgetHistoryData, updateStandardWidgetDisplayValues, type StandardWidgetData } from '@features/hardware/widgets/standardMetricWidget.ts';
import { createStandardHardwareUnitConfig } from '@features/hardware/widgets/unitDefaults.ts';

type MetricsConfigMap = ReturnType<BaseHardwareWidget['getMetricsConfig']>;
type UnitSettingsMap = ReturnType<BaseHardwareWidget['getUnitConfig']>;
type HistoryInput = HardwareWidgetHistoryData;
type GPUDataPoint = HardwareWidgetDataPoint;
type MetricKey = keyof typeof GPU_METRICS;

type GPUData = StandardWidgetData;

interface GPUConfig extends WidgetConfig<GPUDeviceData> {
    index?: number | undefined;
}

interface DeviceNameParts {
    primary: string;
    secondary: string | null;
}

const GPU_METRICS_MAP: MetricsConfigMap = {
    core: { ...GPU_METRICS.core },
    vram: { ...GPU_METRICS.vram },
    power: { ...GPU_METRICS.power },
    temperature: { ...GPU_METRICS.temperature }
};

class GPUWidget extends BaseHardwareWidget<GPUDeviceData> {
    constructor(options: WidgetOptions<GPUDeviceData>) {
        super(options, { metric: 'core', units: createStandardHardwareUnitConfig('vram') });
    }

    override get config(): GPUConfig {
        return super.config;
    }

    override getWidgetType(): string {
        return 'gpu';
    }

    override getDefaultMetric(): string {
        return 'core';
    }

    override getMetricsConfig(): MetricsConfigMap {
        return GPU_METRICS_MAP;
    }

    override getUnitConfig(): UnitSettingsMap {
        return createStandardHardwareUnitConfig('vram');
    }

    override getWidgetLabel(): string {
        const indexValue = this.config['index'];
        const gpuIndex = isFiniteNumber(indexValue) ? indexValue : 0;
        return i18n.t('hardware.widgets.labels.gpu', { index: gpuIndex });
    }

    override getDeviceNameParts(): DeviceNameParts {
        return {
            primary: resolveHardwareDeviceDisplayName(this.config) ?? i18n.t('hardware.components.gpu'),
            secondary: null
        };
    }

    override getAvailableMetrics(): string[] {
        const available: MetricKey[] = ['core', 'vram'];
        const data = this.getCurrentGpuData();
        if (data) {
            if (hasStandardPowerMetric(data)) available.push('power');
            if (hasStandardTemperatureMetric(data)) available.push('temperature');
        }
        return available;
    }

    override createDataPoint(dataInput: GPUDeviceData): GPUDataPoint {
        return createStandardWidgetDataPoint(this.getNormalizedGpuData(dataInput) ?? {}, 'vram', serverEpochMs());
    }

    override transformHistoricalData(historyData: HistoryInput): GPUDataPoint[] {
        return transformStandardWidgetHistoryData({
            historyData,
            metricKeys: GPU_METRIC_KEYS,
            memoryMetricId: 'vram',
            missingTimestampPolicy: 'throw'
        });
    }

    override updateDisplayValues(): void {
        updateStandardWidgetDisplayValues({
            elements: this.metricValueElements,
            units: this.units,
            data: this.getCurrentGpuData(),
            memoryMetricId: 'vram'
        });
    }

    private getCurrentGpuData(): GPUData | null {
        return this.getNormalizedGpuData(this.config.data);
    }

    private getNormalizedGpuData(source: GPUDeviceData | null | undefined): GPUData | null {
        return normalizeStandardWidgetData(source);
    }
}

export { GPUWidget };
