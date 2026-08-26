/* SoAI - Hardware page data controller [frontend/assets/ts/pages/hardware/controllers/dataController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isHardwareSnapshotResource } from '@core/realtime/streammanager/resources/resourceDecoders.ts';
import type { SystemMetricsResponse } from '@core/api/contracts/systemMetricsContracts.ts';
import { toString } from '@core/normalize.ts';
import { readCoercedFiniteNumberOrNullValue } from '@core/types/numberCoercionReaders.ts';
import { isFiniteNumber, isNullOrUndefined } from '@core/typeGuards.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { HISTORY_CHART_MIN_POINTS, scaleHistoryChartPointCount } from '@features/charts/public.ts';
import { METRIC_CONFIG, normalizeHistoryComponent, normalizeIdentifier } from '@features/hardware/public.ts';
import type { ChartOhlcContract } from '@pages/hardware/contracts/contracts.ts';
import { STR_GPU } from '@pages/hardware/contracts/hardwarePageSupport.ts';
import { getDefaultMetricForDevice, isHistoryComponentSupported, metricSupportsDevice, parseDeviceSelection, resolveSupportedHistoryComponent } from '@pages/hardware/state/hardwareSelection.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { DeviceSelection, HardwareCapabilities, HardwarePageSnapshot, ModuleLoggerFunctionValue } from '@pages/hardware/types.ts';

type SelectionApplyOptions = {
    preferredMetric?: string | null | undefined;
};

type SelectionChange = {
    selection: DeviceSelection;
    deviceChanged: boolean;
    metricChanged: boolean;
    changed: boolean;
};

type HardwareDataControllerDependencies = {
    state: HardwarePageState;
    chartOhlc: ChartOhlcContract;
    logger: ModuleLoggerFunctionValue;
};

class HardwareDataController {
    state: HardwarePageState;
    chartOhlc: ChartOhlcContract;
    logger: ModuleLoggerFunctionValue;

    constructor(dependencies: HardwareDataControllerDependencies) {
        this.state = dependencies.state;
        this.chartOhlc = dependencies.chartOhlc;
        this.logger = dependencies.logger;
    }

    isHistoryComponentSupported(component: JsonValue | null | undefined): boolean {
        return isHistoryComponentSupported(this.state.lastSnapshot ?? null, this.state.supportedHistoryComponents, component);
    }

    resolveSupportedHistoryComponent(component: JsonValue | null | undefined): string {
        return resolveSupportedHistoryComponent(this.state.lastSnapshot ?? null, this.state.supportedHistoryComponents, component);
    }

    parseDeviceSelection(value: JsonValue | null | undefined = this.state.selectedDevice): DeviceSelection {
        return parseDeviceSelection(value, this.state.lastSnapshot ?? null, this.state.supportedHistoryComponents);
    }

    getSelectedHistoryTarget(): DeviceSelection {
        return this.parseDeviceSelection(this.state.selectedDevice);
    }

    isDeviceSelected(component: JsonValue | null | undefined, id: JsonValue | null = null): boolean {
        const target = this.getSelectedHistoryTarget();
        const normalized = normalizeHistoryComponent(toString(component));
        if (target.type !== normalized) return false;
        if (normalized === STR_GPU) return Number(id) === (target.gpuIndex ?? 0);
        return isNullOrUndefined(id) || normalizeIdentifier(normalized, toString(id)) === target.identifierKey;
    }

    ensureMetricForDevice(component: JsonValue | null | undefined): void {
        if (!metricSupportsDevice(this.state.selectedMetric, component, METRIC_CONFIG)) {
            this.state.selectedMetric = getDefaultMetricForDevice(component, METRIC_CONFIG);
        }
    }

    applyDeviceSelection(value: JsonValue | null | undefined, options: SelectionApplyOptions = {}): SelectionChange {
        let parsed: DeviceSelection;
        try {
            parsed = this.parseDeviceSelection(value);
        } catch (error) {
            const runtimeError = ensureError(error);
            this.logger('warn', 'Invalid hardware device selection', runtimeError);
            throw runtimeError;
        }

        const previousDevice = this.state.selectedDevice;
        const previousMetric = this.state.selectedMetric;

        this.state.selectedDevice = parsed.value;
        if (options.preferredMetric && metricSupportsDevice(options.preferredMetric, parsed.type, METRIC_CONFIG)) {
            this.state.selectedMetric = options.preferredMetric;
        }
        this.ensureMetricForDevice(parsed.type);

        const deviceChanged = previousDevice !== this.state.selectedDevice;
        const metricChanged = previousMetric !== this.state.selectedMetric;
        return { selection: parsed, deviceChanged, metricChanged, changed: deviceChanged || metricChanged };
    }

    decodeSnapshot(value: JsonValue | null | undefined): HardwarePageSnapshot {
        if (!isHardwareSnapshotResource(value)) {
            throw new TypeError('Hardware realtime resource must contain a decoded hardware snapshot');
        }
        const snapshot = value;
        this.state.lastSnapshot = snapshot;
        return snapshot;
    }

    setSnapshot(snapshot: HardwarePageSnapshot): HardwarePageSnapshot {
        this.state.lastSnapshot = snapshot;
        return snapshot;
    }

    setMetrics(value: JsonValue | null | undefined): import('@pages/hardware/types.ts').MetricsData | null {
        if (!isJsonObject(value)) return null;
        const metrics: SystemMetricsResponse = value;
        this.state.currentMetrics = metrics;
        return metrics;
    }

    setHardwareCapabilities(payload: HardwareCapabilities): HardwareCapabilities {
        const historyConfig = payload.historyConfig;
        if (!historyConfig) {
            throw new TypeError('hardware.capabilities snapshot must include historyConfig');
        }

        this.state.hardwareCapabilities = payload;

        const intervalsRaw = historyConfig.supportedIntervalsMs;
        this.state.supportedHistoryIntervalsMs = (intervalsRaw ?? [])
            .map(Number)
            .filter(isFiniteNumber)
            .sort((firstValue: number, secondValue: number) => firstValue - secondValue);

        const aggregationsRaw = historyConfig.supportedAggregations;
        this.state.supportedHistoryAggregations = (aggregationsRaw ?? []).map((entry) => entry.toLowerCase()).filter(Boolean);

        const componentsRaw = historyConfig.components;
        if (componentsRaw?.length) {
            this.state.supportedHistoryComponents = componentsRaw.map((component) => normalizeHistoryComponent(toString(component)));
        }

        this.updateRetentionConfig(historyConfig);
        return payload;
    }

    updateRetentionConfig(historyConfig: import('@pages/hardware/types.ts').HistoryConfig): void {
        const retentionHours = readCoercedFiniteNumberOrNullValue(historyConfig.retentionHours);
        if (retentionHours !== null && retentionHours > 0) {
            this.state.maxRetentionMinutes = Math.max(1, Math.round(retentionHours * 60));
        }

        const monitoringIntervalMs = readCoercedFiniteNumberOrNullValue(historyConfig.loggingIntervalMs);
        if (monitoringIntervalMs !== null && monitoringIntervalMs > 0) {
            this.state.monitoringIntervalMs = Math.max(1, Math.round(monitoringIntervalMs));
        }

        const maxPoints = readCoercedFiniteNumberOrNullValue(historyConfig.maxPoints);
        if (maxPoints !== null && maxPoints > 0) {
            const bounded = Math.min(this.state.chartHardLimit, scaleHistoryChartPointCount(maxPoints));
            this.state.maxHistoryPoints = this.state.historyApiPointCap = Math.max(HISTORY_CHART_MIN_POINTS, bounded);
        }

        const estimated = this.state.maxRetentionMinutes ? Math.ceil((this.state.maxRetentionMinutes * 60_000) / Math.max(1, this.state.monitoringIntervalMs)) : this.state.maxHistoryPoints;
        const scaledEstimated = scaleHistoryChartPointCount(estimated || this.state.maxHistoryPoints);
        this.state.maxHistoryPoints = Math.max(HISTORY_CHART_MIN_POINTS, Math.min(this.state.chartHardLimit, scaledEstimated));
    }
}

export { HardwareDataController };
export type { HardwareDataControllerDependencies, SelectionApplyOptions, SelectionChange };
