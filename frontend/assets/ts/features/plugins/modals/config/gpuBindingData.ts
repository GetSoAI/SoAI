/* SoAI - Plugins feature GPU binding data [frontend/assets/ts/features/plugins/modals/config/gpuBindingData.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareGpuSnapshot, HardwareSnapshotResponse } from '@core/api/contracts/hardwareContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedLower } from '@core/normalize.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { PLUGIN_GPU_ALL_ID, PLUGIN_GPU_BINDING_KEY, type PluginGpuBindingBadgeTone, type PluginGpuBindingEntry, type PluginGpuBindingSelection, type PluginGpuBindingSelectorState } from '@features/plugins/modals/config/gpuBindingTypes.ts';

const readStringField = (source: HardwareGpuSnapshot, keys: readonly (keyof HardwareGpuSnapshot)[]): string | null => {
    for (const key of keys) {
        const value = source[key];
        if (typeof value === 'string' && value.trim()) {
            return value.trim();
        }
    }
    return null;
};

const readNumberField = (source: HardwareGpuSnapshot, keys: readonly (keyof HardwareGpuSnapshot)[]): number | null => {
    for (const key of keys) {
        const value = source[key];
        if (isFiniteNumber(value)) {
            return value;
        }
    }
    return null;
};

const isNonEmptyStringValue = (value: JsonValue): value is string => typeof value === 'string' && value.trim().length > 0;

const vendorBrand = (vendor: string | null): { badge: string; tone: PluginGpuBindingBadgeTone } => {
    const normalized = toTrimmedLower(vendor ?? '');
    if (normalized.includes('nvidia')) {
        return { badge: 'NVIDIA', tone: 'nvidia' };
    }
    if (normalized.includes('amd') || normalized.includes('advancedmicrodevices')) {
        return { badge: 'AMD', tone: 'amd' };
    }
    if (normalized.includes('intel')) {
        return { badge: 'INTEL', tone: 'intel' };
    }
    return { badge: i18n.t('plugins.modal.config.gpuUnknownBadge'), tone: 'neutral' };
};

const hasInactiveGpuRuntime = (entry: HardwareGpuSnapshot): boolean => {
    const reason = readStringField(entry, ['telemetryUnavailableReason']);
    if (toTrimmedLower(reason ?? '') === 'driver_inactive') {
        return true;
    }
    const kernelDriver = readStringField(entry, ['kernelDriver']);
    return toTrimmedLower(kernelDriver ?? '') === 'nouveau';
};

const isGpuBindingEligibleRecord = (entry: HardwareGpuSnapshot): boolean => {
    if (!readStringField(entry, ['deviceId'])) {
        return false;
    }
    if (entry.computeCapable === false || hasInactiveGpuRuntime(entry)) {
        return false;
    }
    const memoryMb = readNumberField(entry, ['memoryTotalMb']);
    return memoryMb === null || memoryMb > 0;
};

const formatMemoryGb = (memoryGb: number): string => i18n.formatNumber(memoryGb, { maximumFractionDigits: 1 });

const deviceDetail = (entry: HardwareGpuSnapshot, deviceId: string): string => {
    const slot = readStringField(entry, ['pciBdf', 'gpuUuid']) ?? deviceId;
    const index = readNumberField(entry, ['bindingIndex', 'index']);
    if (index !== null) {
        return i18n.t('plugins.modal.config.gpuDeviceDetailWithIndex', {
            index: i18n.formatNumber(index, { maximumFractionDigits: 0 }),
            slot
        });
    }
    return i18n.t('plugins.modal.config.gpuDeviceDetail', { slot });
};

const createGpuEntry = (entry: HardwareGpuSnapshot): PluginGpuBindingEntry | null => {
    const id = readStringField(entry, ['deviceId']);
    if (!id) {
        return null;
    }
    const label = readStringField(entry, ['label', 'name']) ?? id;
    const vendor = vendorBrand(readStringField(entry, ['vendor', 'type']));
    const memoryMb = readNumberField(entry, ['memoryTotalMb']) ?? 0;
    const memoryGb = Math.max(0, memoryMb) / 1024;
    const description = memoryGb > 0 ? i18n.t('plugins.modal.config.gpuMemoryLabel', { memory: formatMemoryGb(memoryGb) }) : i18n.t('plugins.modal.config.gpuMemoryUnavailable');
    const detail = deviceDetail(entry, id);
    return {
        id,
        label,
        badge: vendor.badge,
        badgeTone: vendor.tone,
        description,
        detail,
        memoryTotalGb: memoryGb,
        haystack: toTrimmedLower(`${label} ${vendor.badge} ${description} ${detail}`)
    };
};

const isPluginGpuBindingEntry = (entry: PluginGpuBindingEntry | null): entry is PluginGpuBindingEntry => entry !== null;

const gpuRecords = (snapshot: HardwareSnapshotResponse): HardwareGpuSnapshot[] => {
    const gpu = snapshot.gpu;
    if (!gpu) {
        return [];
    }
    const bindingDevices = gpu.binding?.devices ?? [];
    const records = bindingDevices.length > 0 ? bindingDevices : gpu.gpus;
    return records.filter(isGpuBindingEligibleRecord);
};

const allGpuEntry = (): PluginGpuBindingEntry => {
    return {
        id: PLUGIN_GPU_ALL_ID,
        label: i18n.t('plugins.modal.config.gpuAllLabel'),
        badge: i18n.t('plugins.modal.config.gpuAllBadge'),
        badgeTone: 'neutral',
        description: i18n.t('plugins.modal.config.gpuAllDescription'),
        detail: i18n.t('plugins.modal.config.gpuAllDetail'),
        memoryTotalGb: 0,
        haystack: toTrimmedLower(`${i18n.t('plugins.modal.config.gpuAllLabel')} ${i18n.t('plugins.modal.config.gpuAllDescription')}`)
    };
};

const parseBindingSelection = (value: JsonValue | undefined): PluginGpuBindingSelection => {
    if (!isJsonObject(value)) {
        return { mode: 'all', deviceIds: [] };
    }
    const modeValue = value['mode'];
    const deviceIdsValue = value['device_ids'];
    const deviceIds = Array.isArray(deviceIdsValue) ? deviceIdsValue.filter(isNonEmptyStringValue).map((item) => item.trim()) : [];
    return modeValue === 'selected' && deviceIds.length > 0 ? { mode: 'selected', deviceIds } : { mode: 'all', deviceIds: [] };
};

const selectedIdsForEntries = (config: JsonObject, entries: readonly PluginGpuBindingEntry[]): string[] => {
    const availableIds = new Set(entries.map((entry) => entry.id));
    const selection = parseBindingSelection(config[PLUGIN_GPU_BINDING_KEY]);
    const selected = selection.mode === 'selected' ? selection.deviceIds.filter((id) => availableIds.has(id)) : [];
    return selected.length > 0 ? selected : [PLUGIN_GPU_ALL_ID];
};

const pluginSupportsGpuBinding = (plugin: PluginRecord): boolean => plugin.capabilities?.supportsGpuBinding === true;

const buildPluginGpuBindingSelectorState = (plugin: PluginRecord, config: JsonObject, snapshot: HardwareSnapshotResponse): PluginGpuBindingSelectorState | null => {
    if (!pluginSupportsGpuBinding(plugin)) {
        return null;
    }
    const gpuEntries = gpuRecords(snapshot).map(createGpuEntry).filter(isPluginGpuBindingEntry);
    if (gpuEntries.length === 0) {
        return null;
    }
    const entries = [allGpuEntry(), ...gpuEntries];
    return {
        entries,
        selectedIds: selectedIdsForEntries(config, entries)
    };
};

export { buildPluginGpuBindingSelectorState, pluginSupportsGpuBinding };
