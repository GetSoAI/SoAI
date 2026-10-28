/* SoAI - Hardware feature network widget [frontend/assets/ts/features/hardware/widgets/NetworkWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampPercent } from '@core/primitives/clampNumber.ts';
import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { formatSpeedValue } from '@features/hardware/Formatters.ts';
import { BaseHardwareWidget } from '@features/hardware/widgets/BaseHardwareWidget.ts';
import type { HardwareWidgetDataPoint, HardwareWidgetHistoryData, MetricChartNormalizer, WidgetConfig, WidgetOptions } from '@features/hardware/widgets/contracts.ts';
import { NETWORK_METRICS } from '@features/hardware/widgets/constants.ts';
import type { NetworkDeviceData } from '@features/hardware/widgets/internalContracts.ts';
import { resolveNumericMetric } from '@features/hardware/widgets/metricValues.ts';

type MetricsConfigMap = ReturnType<BaseHardwareWidget['getMetricsConfig']>;
type UnitSettingsMap = ReturnType<BaseHardwareWidget['getUnitConfig']>;
type HistoryInput = HardwareWidgetHistoryData;
type NetworkDataPoint = HardwareWidgetDataPoint;

interface NetworkData {
    downloadMbps?: number | undefined;
    uploadMbps?: number | undefined;
    linkSpeedMbps?: number | undefined;
}

interface NetworkConfig extends WidgetConfig<NetworkDeviceData> {
    index?: number | undefined;
    deviceId?: string | undefined;
}

const NETWORK_METRICS_MAP: MetricsConfigMap = {
    download: { ...NETWORK_METRICS.download },
    upload: { ...NETWORK_METRICS.upload }
};

const normalizeNetworkWidgetData = (source: NetworkDeviceData | null | undefined): NetworkData => ({
    downloadMbps: isFiniteNumber(source?.downloadMbps) ? source.downloadMbps : undefined,
    uploadMbps: isFiniteNumber(source?.uploadMbps) ? source.uploadMbps : undefined,
    linkSpeedMbps: isFiniteNumber(source?.linkSpeedMbps) ? source.linkSpeedMbps : undefined
});

class NetworkWidget extends BaseHardwareWidget<NetworkDeviceData> {
    constructor(options: WidgetOptions<NetworkDeviceData>) {
        super(options, { metric: 'download', units: {} });
    }

    override get config(): NetworkConfig {
        return super.config;
    }

    override getWidgetType(): string {
        return 'network';
    }

    override getDefaultMetric(): string {
        return 'download';
    }

    override getMetricsConfig(): MetricsConfigMap {
        return NETWORK_METRICS_MAP;
    }

    override getUnitConfig(): UnitSettingsMap {
        return {};
    }

    override getWidgetLabel(): string {
        return i18n.t('hardware.widgets.labels.network', { index: this.config.index ?? 0 });
    }

    override getDeviceNameParts(): { primary: string; secondary: string | null } {
        return {
            primary: this.config.name ?? i18n.t('hardware.cards.network.labels.card'),
            secondary: null
        };
    }

    override getAvailableMetrics(): string[] {
        return ['download', 'upload'];
    }

    override createDataPoint(dataInput: NetworkDeviceData): NetworkDataPoint {
        const data = normalizeNetworkWidgetData(dataInput);
        return {
            download: data.downloadMbps,
            upload: data.uploadMbps,
            timestamp: serverEpochMs()
        };
    }

    override transformHistoricalData(historyData: HistoryInput): NetworkDataPoint[] {
        const timestamps = Array.isArray(historyData.timestampsMs) ? historyData.timestampsMs : [];
        const dataRows = Array.isArray(historyData.data) ? historyData.data : [];
        const points: NetworkDataPoint[] = [];
        const limit = Math.min(timestamps.length, dataRows.length);
        for (let index = 0; index < limit; index += 1) {
            const timestamp = timestamps[index];
            const row = dataRows[index];
            if (!isFiniteNumber(timestamp) || !row) {
                continue;
            }
            points.push({
                download: resolveNumericMetric(row, ['download_mbps']) ?? undefined,
                upload: resolveNumericMetric(row, ['upload_mbps']) ?? undefined,
                timestamp
            });
        }
        return points;
    }

    override updateDisplayValues(): void {
        const data = normalizeNetworkWidgetData(this.config.data);
        const downloadElement = this.metricValueElements['download'];
        if (downloadElement) {
            dom.setText(downloadElement, isFiniteNumber(data.downloadMbps) ? formatSpeedValue(data.downloadMbps) : i18n.t('common.notAvailableShort'));
        }
        const uploadElement = this.metricValueElements['upload'];
        if (uploadElement) {
            dom.setText(uploadElement, isFiniteNumber(data.uploadMbps) ? formatSpeedValue(data.uploadMbps) : i18n.t('common.notAvailableShort'));
        }
    }

    protected override createChartMetricNormalizer(): MetricChartNormalizer {
        let denominator: number | null = null;
        return (value, metric) => {
            denominator ??= this.#resolveChartDenominator(metric);
            return denominator > 0 ? clampPercent((value / denominator) * 100) : 0;
        };
    }

    override normalizeChartMetricValue(value: number, metric: string): number {
        const denominator = this.#resolveChartDenominator(metric);
        return denominator > 0 ? clampPercent((value / denominator) * 100) : 0;
    }

    #resolveChartDenominator(metric: string): number {
        const data = normalizeNetworkWidgetData(this.config.data);
        const linkSpeed = data.linkSpeedMbps ?? 0;
        if (linkSpeed > 0) {
            return linkSpeed;
        }
        return this.dataPoints.reduce((max, point) => {
            const metricValue = point[metric];
            return isFiniteNumber(metricValue) ? Math.max(max, metricValue) : max;
        }, 0);
    }
}

export { NetworkWidget };
