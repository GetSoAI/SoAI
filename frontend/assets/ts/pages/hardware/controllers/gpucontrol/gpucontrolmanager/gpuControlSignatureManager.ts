/* SoAI - Hardware page GPU control signature manager [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolmanager/gpuControlSignatureManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { GPU_SLIDER_CONFIG } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';
import type { GpuCapabilitiesByIndex, GpuCapabilityControlInfo, GpuClockCapabilityInfo } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { GpuSavedSettingsState, GpuSlotEntry } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

const entries = Object.entries;

type SignatureValue = string | number | boolean | null | SignatureValue[] | { [key: string]: SignatureValue };

const serializeSignature = (value: SignatureValue): string => JSON.stringify(value);

const sortedRecord = (record: Record<string, SignatureValue>): Record<string, SignatureValue> => {
    const sorted: Record<string, SignatureValue> = {};
    entries(record)
        .sort(([left], [right]) => left.localeCompare(right, 'en'))
        .forEach(([key, value]) => {
            sorted[key] = value;
        });
    return sorted;
};

const capabilitySignature = (capability: GpuCapabilityControlInfo | GpuClockCapabilityInfo | undefined): SignatureValue => {
    if (!capability) {
        return null;
    }
    return sortedRecord({
        supported: capability.supported === true,
        min: typeof capability.min === 'number' ? capability.min : null,
        max: typeof capability.max === 'number' ? capability.max : null,
        minimum: typeof capability.minimum === 'number' ? capability.minimum : null,
        maximum: typeof capability.maximum === 'number' ? capability.maximum : null,
        default: typeof capability.default === 'number' ? capability.default : null,
        step: typeof capability.step === 'number' ? capability.step : null,
        ticks: typeof capability.ticks === 'number' ? capability.ticks : null,
        offsetMin: 'offsetMin' in capability && typeof capability.offsetMin === 'number' ? capability.offsetMin : null,
        offsetMax: 'offsetMax' in capability && typeof capability.offsetMax === 'number' ? capability.offsetMax : null,
        unsupportedReason: typeof capability.unsupportedReason === 'string' ? capability.unsupportedReason : null,
        controlBackend: typeof capability.controlBackend === 'string' ? capability.controlBackend : null
    });
};

const settingsSignature = (settings: Record<string, JsonValue> | undefined): SignatureValue => {
    if (!settings) {
        return null;
    }
    const result: Record<string, SignatureValue> = {};
    entries(settings).forEach(([key, value]) => {
        if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' || value === null) {
            result[key] = value;
        }
    });
    return sortedRecord(result);
};

const slotEntrySignature = (entry: GpuSlotEntry): SignatureValue => {
    const slots: Record<string, SignatureValue> = {};
    entries(entry.slots ?? {}).forEach(([slot, slotData]) => {
        slots[slot] = sortedRecord({
            settings: settingsSignature(slotData.settings),
            fieldModes: settingsSignature(slotData.fieldModes)
        });
    });
    return sortedRecord({
        deviceId: entry.deviceId ?? null,
        gpuIndex: typeof entry.gpuIndex === 'number' ? entry.gpuIndex : null,
        bootEnabledSaved: entry.boot?.enabled === true,
        bootSlotSaved: entry.boot?.slot ?? null,
        slots: sortedRecord(slots)
    });
};

const buildGpuCapabilitiesRenderSignature = (capabilities: GpuCapabilitiesByIndex | null): string => {
    if (!capabilities) {
        return '';
    }
    const result: Record<string, SignatureValue> = {};
    entries(capabilities).forEach(([index, gpu]) => {
        const controls: Record<string, SignatureValue> = {};
        GPU_SLIDER_CONFIG.forEach(({ capabilityKey }) => {
            controls[capabilityKey] = capabilitySignature(gpu[capabilityKey]);
        });
        result[index] = sortedRecord({
            deviceId: gpu.deviceId ?? null,
            index: typeof gpu.index === 'number' || typeof gpu.index === 'string' ? String(gpu.index) : null,
            name: gpu.name ?? null,
            type: gpu.type ?? null,
            controls: sortedRecord(controls)
        });
    });
    return serializeSignature(sortedRecord(result));
};

const buildGpuSlotsRenderSignature = (settings: GpuSavedSettingsState | null): string => {
    if (!settings) {
        return '';
    }
    const result: Record<string, SignatureValue> = {};
    entries(settings.byIndex ?? {}).forEach(([index, entry]) => {
        result[index] = slotEntrySignature(entry);
    });
    return serializeSignature(sortedRecord(result));
};

export { buildGpuCapabilitiesRenderSignature, buildGpuSlotsRenderSignature };
