/* SoAI - Hardware page mapping [frontend/assets/ts/pages/hardware/mappers/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { extractUserFacingErrorMessage } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatInvariantNumber } from '@core/localization/public.ts';
import { readCoercedFiniteNumberOrNullValue } from '@core/types/numberCoercionReaders.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { METRIC_CONFIG, buildNetworkInterfaceModels, buildVolumeModels, DEFAULT_IGNORED_NETWORK_PREFIXES, getCpuDevices, getGpuDevices, getGpuOptionId, normalizeHistoryComponent, resolveHardwareDeviceDisplayName, type NetworkInterfaceModel, type VolumeModel } from '@features/hardware/public.ts';
import { STR_CPU, STR_DISK, STR_GPU, STR_NETWORK } from '@pages/hardware/contracts/hardwarePageSupport.ts';
import { buildDeviceSelectionValue, isHistoryComponentSupported, metricSupportsDevice } from '@pages/hardware/state/hardwareSelection.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { CategoryOption, MetricOption } from '@pages/hardware/types.ts';

const buildDeviceCategoryOptions = (state: HardwarePageState): CategoryOption[] => {
    const seen = new Set<string>();
    const list: CategoryOption[] = [];
    const add = (value: string, label: string): void => {
        if (!seen.has(value)) {
            list.push({ value, label });
            seen.add(value);
        }
    };

    const cpuDevices = getCpuDevices(state.lastSnapshot);
    const firstCpu = cpuDevices[0];
    if (firstCpu) {
        const cpuName = resolveHardwareDeviceDisplayName(firstCpu);
        const socketId = Number(firstCpu.socketId);
        const cpuIndex = isFiniteNumber(socketId) ? Math.max(0, Math.floor(socketId)) : 0;
        add(STR_CPU, cpuName ? i18n.t('hardware.devices.cpuEntry', { index: cpuIndex, name: cpuName }) : i18n.t('hardware.devices.cpu'));
    }
    if (isHistoryComponentSupported(state.lastSnapshot ?? null, state.supportedHistoryComponents, STR_GPU)) {
        getGpuDevices(state.lastSnapshot).forEach((gpu, index: number) =>
            add(
                buildDeviceSelectionValue(STR_GPU, getGpuOptionId(gpu, index)),
                (() => {
                    const gpuName = resolveHardwareDeviceDisplayName(gpu);
                    const nameSuffix = gpuName ? ` · ${gpuName}` : '';
                    return `${i18n.t('hardware.devices.gpu')} ${getGpuOptionId(gpu, index)}${nameSuffix}`;
                })()
            )
        );
    }
    if (isHistoryComponentSupported(state.lastSnapshot ?? null, state.supportedHistoryComponents, STR_DISK)) {
        buildVolumeModels(state.lastSnapshot).forEach((volume: VolumeModel) => {
            add(buildDeviceSelectionValue(STR_DISK, volume.deviceId), `${i18n.t('hardware.devices.disk')} · ${volume.mount}`);
        });
    }
    if (isHistoryComponentSupported(state.lastSnapshot ?? null, state.supportedHistoryComponents, STR_NETWORK)) {
        buildNetworkInterfaceModels(state.lastSnapshot, { ignorePrefixes: DEFAULT_IGNORED_NETWORK_PREFIXES }).forEach((network: NetworkInterfaceModel) => {
            add(buildDeviceSelectionValue(STR_NETWORK, network.deviceId), `${i18n.t('hardware.devices.network')} · ${network.name}`);
        });
    }
    if (!list.length) add(STR_CPU, i18n.t('hardware.devices.cpu'));
    return list;
};

const buildMetricOptions = (state: HardwarePageState, type: string | null | undefined, selected: string = state.selectedMetric): MetricOption[] => {
    const normalized = normalizeHistoryComponent(type);
    const options: MetricOption[] = [];
    for (const metricKey in METRIC_CONFIG) {
        if (!metricSupportsDevice(metricKey, normalized, METRIC_CONFIG)) continue;
        const config = METRIC_CONFIG[metricKey];
        options.push({
            value: metricKey,
            label: config?.label ? config.label() : metricKey,
            selected: metricKey === selected
        });
    }
    return options;
};

const getMetricKey = (metricId: string, componentType: string): string | undefined => {
    const metricKey = String(metricId ?? '');
    const config = METRIC_CONFIG[metricKey];
    if (!config) {
        return undefined;
    }
    const deviceType = normalizeHistoryComponent(componentType);
    const key = config.realtimeKeyByDevice[deviceType];
    return typeof key === 'string' && key ? key : undefined;
};

const getHistoryMetricKey = (metricId: string, componentType: string): string | undefined => {
    const metricKey = String(metricId ?? '');
    const config = METRIC_CONFIG[metricKey];
    if (!config) {
        return undefined;
    }
    const deviceType = normalizeHistoryComponent(componentType);
    const key = config.historyKeyByDevice[deviceType];
    return typeof key === 'string' && key ? key : undefined;
};

const getMetricLabel = (state: HardwarePageState): string => {
    const config = METRIC_CONFIG[state.selectedMetric];
    return config?.label ? config.label() : i18n.t('hardware.metrics.labels.default', { label: state.selectedMetric });
};

const formatMetricValue = (state: HardwarePageState, value: number): string => {
    const numeric = readCoercedFiniteNumberOrNullValue(value);
    if (numeric === null) return i18n.t('common.notAvailableShort');
    const config = METRIC_CONFIG[state.selectedMetric];
    return config?.format ? config.format(numeric) : formatInvariantNumber(numeric, { maximumFractionDigits: 1 });
};

const getMetricScaleBounds = (state: HardwarePageState): { min?: number | undefined; max?: number | undefined } | null => {
    const bounds = METRIC_CONFIG[state.selectedMetric]?.bounds;
    if (!bounds) return null;
    const resolved: { min?: number | undefined; max?: number | undefined } = {};
    if (isFiniteNumber(bounds['min'])) resolved['min'] = bounds['min'];
    if (isFiniteNumber(bounds['max'])) resolved['max'] = bounds['max'];
    return Object.keys(resolved).length ? resolved : null;
};

const formatHistoryErrorMessage = (error: Error): string => {
    const base = i18n.t('hardware.errors.historyInitFailed');
    const candidate = extractUserFacingErrorMessage(error);
    return candidate && candidate !== base && !base.includes(candidate) ? `${base}: ${candidate}` : candidate || base;
};

export { buildDeviceCategoryOptions, buildMetricOptions, formatHistoryErrorMessage, formatMetricValue, getHistoryMetricKey, getMetricKey, getMetricLabel, getMetricScaleBounds };
