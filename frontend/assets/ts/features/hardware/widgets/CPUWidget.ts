/* SoAI - Hardware feature cpu widget [frontend/assets/ts/features/hardware/widgets/CPUWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { BaseHardwareWidget } from '@features/hardware/widgets/BaseHardwareWidget.ts';
import { resolveHardwareDeviceDisplayName } from '@features/hardware/deviceNames.ts';
import type { HardwareWidgetDataPoint, HardwareWidgetHistoryData, WidgetConfig, WidgetOptions } from '@features/hardware/widgets/contracts.ts';
import { CPU_METRICS } from '@features/hardware/widgets/constants.ts';
import type { CPUDeviceData } from '@features/hardware/widgets/internalContracts.ts';
import { CPU_METRIC_KEYS } from '@features/hardware/widgets/metricKeysRegistry.ts';
import { createStandardWidgetDataPoint, hasStandardPowerMetric, hasStandardTemperatureMetric, normalizeStandardWidgetData, transformStandardWidgetHistoryData, updateStandardWidgetDisplayValues, type StandardWidgetData } from '@features/hardware/widgets/standardMetricWidget.ts';
import { createStandardHardwareUnitConfig } from '@features/hardware/widgets/unitDefaults.ts';

type MetricsConfigMap = ReturnType<BaseHardwareWidget['getMetricsConfig']>;
type UnitSettingsMap = ReturnType<BaseHardwareWidget['getUnitConfig']>;
type HistoryInput = HardwareWidgetHistoryData;
type CPUDataPoint = HardwareWidgetDataPoint;

type CPUData = StandardWidgetData;

interface CPUConfig extends WidgetConfig<CPUDeviceData> {
    socketIndex?: number | undefined;
    sockets?: number | undefined;
    cores?: number | undefined;
    threads?: number | undefined;
}

const CPU_METRICS_MAP: MetricsConfigMap = {
    core: { ...CPU_METRICS.core },
    ram: { ...CPU_METRICS.ram },
    power: { ...CPU_METRICS.power },
    temperature: { ...CPU_METRICS.temperature }
};

class CPUWidget extends BaseHardwareWidget<CPUDeviceData> {
    constructor(options: WidgetOptions<CPUDeviceData>) {
        super(options, { metric: 'core', units: createStandardHardwareUnitConfig('ram') });
    }

    override get config(): CPUConfig {
        return super.config;
    }

    override getWidgetType(): string {
        return 'cpu';
    }

    override getDefaultMetric(): string {
        return 'core';
    }

    override getMetricsConfig(): MetricsConfigMap {
        return CPU_METRICS_MAP;
    }

    override getUnitConfig(): UnitSettingsMap {
        return createStandardHardwareUnitConfig('ram');
    }

    override getWidgetLabel(): string {
        const socketIndex = this.config.socketIndex ?? 0;
        return i18n.t('hardware.widgets.labels.cpu', { index: socketIndex });
    }

    override getDeviceNameParts(): { primary: string; secondary: string | null } {
        const name = resolveHardwareDeviceDisplayName(this.config) ?? i18n.t('hardware.components.cpu');
        const parts: string[] = [];
        if (this.config.sockets && this.config.sockets > 1) parts.push(`${this.config.sockets}x`);
        if (this.config.cores && this.config.cores > 0) parts.push(`${this.config.cores}c/${this.config.threads}t`);
        const secondary: string | null = parts.length > 0 ? parts.join(' ') : null;
        return { primary: name, secondary: secondary };
    }

    override getAvailableMetrics(): string[] {
        const available: string[] = ['core', 'ram'];
        const data = this.getCurrentCpuData();
        if (data) {
            if (hasStandardPowerMetric(data)) available.push('power');
            if (hasStandardTemperatureMetric(data)) available.push('temperature');
        }
        return available;
    }

    override createDataPoint(dataInput: CPUDeviceData): CPUDataPoint {
        return createStandardWidgetDataPoint(this.getNormalizedCpuData(dataInput) ?? {}, 'ram', serverEpochMs());
    }

    override transformHistoricalData(historyData: HistoryInput): CPUDataPoint[] {
        return transformStandardWidgetHistoryData({
            historyData,
            metricKeys: CPU_METRIC_KEYS,
            memoryMetricId: 'ram',
            missingTimestampPolicy: 'skip'
        });
    }

    override updateDisplayValues(): void {
        updateStandardWidgetDisplayValues({
            elements: this.metricValueElements,
            units: this.units,
            data: this.getCurrentCpuData(),
            memoryMetricId: 'ram'
        });
    }

    private getCurrentCpuData(): CPUData | null {
        return this.getNormalizedCpuData(this.config.data);
    }

    private getNormalizedCpuData(source: CPUDeviceData | null | undefined): CPUData | null {
        return normalizeStandardWidgetData(source);
    }
}

export { CPUWidget };
