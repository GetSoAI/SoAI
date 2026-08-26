/* SoAI - Shared realtime GPU capabilities resource [frontend/assets/ts/core/realtime/streammanager/resources/gpuCapabilitiesResource.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeClockCapability, decodeControlCapability, decodeCurrentSettings, decodeError, optionalNumber, optionalText, type GpuCapabilities, type GpuCapabilitiesResource } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { ResourceContext } from '@core/realtime/streammanager/types.ts';
import { hasOwn, isBoolean, isFiniteNumber, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { toJsonCompatibleObject } from '@core/primitives/clone.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';

const keys = Object.keys;

const decodeStringList = (value: JsonValue | undefined, label: string): string[] | undefined => {
    if (value === undefined || value === null) return undefined;
    if (!Array.isArray(value) || !value.every(isString)) throw new TypeError(`${label} must be a string array`);
    return [...value];
};

const decodeLiveState = (value: JsonValue | undefined, label: string): GpuCapabilities['live'] => {
    if (value === undefined || value === null) return undefined;
    const record = requireRecord(value, label);
    if (hasOwn(record, 'activeSlot') || hasOwn(record, 'currentSettings')) throw new TypeError(`${label} must use canonical V1 wire fields`);
    const live: NonNullable<GpuCapabilities['live']> = {
        currentSettings: decodeCurrentSettings(record['current_settings'], `${label}.current_settings`)
    };
    const activeSlot = optionalText(record, 'active_slot', label);
    const bootSlot = optionalText(record, 'boot_slot', label);
    if (activeSlot !== undefined) live.activeSlot = activeSlot;
    if (bootSlot !== undefined) live.bootSlot = bootSlot;
    return live;
};

const decodeGpuCapabilities = (value: JsonValue, label: string): GpuCapabilities => {
    const record = requireRecord(value, label);
    if (hasOwn(record, 'deviceId') || hasOwn(record, 'vendorId') || hasOwn(record, 'controlBackends') || hasOwn(record, 'powerLimitWatts') || hasOwn(record, 'activeSlot') || hasOwn(record, 'currentSettings')) {
        throw new TypeError(`${label} must use canonical V1 wire fields`);
    }
    const capabilities: GpuCapabilities = {};
    const index = record['index'];
    if (index !== undefined && index !== null) {
        if (!isString(index) && !isFiniteNumber(index)) throw new TypeError(`${label}.index must be a string or finite number`);
        capabilities.index = index;
    }
    const deviceId = optionalText(record, 'device_id', label);
    const vendor = optionalText(record, 'vendor', label);
    const vendorId = optionalNumber(record, 'vendor_id', label);
    const pciBdf = optionalText(record, 'pci_bdf', label);
    const operatingSystem = optionalText(record, 'os', label);
    const driver = optionalText(record, 'driver', label);
    const type = optionalText(record, 'type', label);
    const name = optionalText(record, 'name', label);
    const displayName = optionalText(record, 'display_name', label);
    const controlBackends = decodeStringList(record['control_backends'], `${label}.control_backends`);
    if (deviceId !== undefined && deviceId !== null) capabilities.deviceId = deviceId;
    if (vendor !== undefined && vendor !== null) capabilities.vendor = vendor;
    if (vendorId !== undefined) capabilities.vendorId = vendorId;
    if (pciBdf !== undefined) capabilities.pciBdf = pciBdf;
    if (operatingSystem !== undefined && operatingSystem !== null) capabilities.os = operatingSystem;
    if (driver !== undefined) capabilities.driver = driver;
    if (type !== undefined && type !== null) capabilities.type = type;
    if (name !== undefined && name !== null) capabilities.name = name;
    if (displayName !== undefined && displayName !== null) capabilities.displayName = displayName;
    if (controlBackends !== undefined) capabilities.controlBackends = controlBackends;
    const powerLimitWatts = decodeControlCapability(record['power_limit_watts'], `${label}.power_limit_watts`);
    const coreClockMhz = decodeClockCapability(record['core_clock_mhz'], `${label}.core_clock_mhz`);
    const memClockMhz = decodeClockCapability(record['mem_clock_mhz'], `${label}.mem_clock_mhz`);
    const fanSpeedPercent = decodeControlCapability(record['fan_speed_percent'], `${label}.fan_speed_percent`);
    if (powerLimitWatts) capabilities.powerLimitWatts = powerLimitWatts;
    if (coreClockMhz) capabilities.coreClockMhz = coreClockMhz;
    if (memClockMhz) capabilities.memClockMhz = memClockMhz;
    if (fanSpeedPercent) capabilities.fanSpeedPercent = fanSpeedPercent;
    const activeSlot = optionalText(record, 'active_slot', label);
    const bootSlot = optionalText(record, 'boot_slot', label);
    if (activeSlot !== undefined) capabilities.activeSlot = activeSlot;
    if (bootSlot !== undefined) capabilities.bootSlot = bootSlot;
    if (record['current_settings'] !== undefined) capabilities.currentSettings = decodeCurrentSettings(record['current_settings'], `${label}.current_settings`);
    const live = decodeLiveState(record['live'], `${label}.live`);
    if (live) capabilities.live = live;
    return capabilities;
};

const decodeGpuMap = (value: JsonValue | undefined, label: string): Record<string, GpuCapabilities> & JsonObject => {
    const record = requireRecord(value, label);
    const decoded: Record<string, GpuCapabilities> & JsonObject = {};
    for (const [key, entry] of Object.entries(record)) decoded[key] = decodeGpuCapabilities(entry, `${label}.${key}`);
    return decoded;
};

const decodeGpuCapabilitiesResource = (payload: JsonValue | null): GpuCapabilitiesResource => {
    const record = requireRecord(payload, 'GPU capabilities resource payload');
    if (hasOwn(record, 'gpusByDeviceId') || hasOwn(record, 'computeDrivers') || hasOwn(record, 'totalVramGb')) throw new TypeError('GPU capabilities resource payload must use canonical V1 wire fields');
    const success = record['success'];
    const totalVramGb = record['total_vram_gb'];
    if (!isBoolean(success)) throw new TypeError('GPU capabilities resource payload.success must be a boolean');
    if (!isFiniteNumber(totalVramGb)) throw new TypeError('GPU capabilities resource payload.total_vram_gb must be a finite number');
    const decoded: GpuCapabilitiesResource = {
        success,
        gpus: decodeGpuMap(record['gpus'], 'GPU capabilities resource payload.gpus'),
        gpusByDeviceId: decodeGpuMap(record['gpus_by_device_id'], 'GPU capabilities resource payload.gpus_by_device_id'),
        computeDrivers: toJsonCompatibleObject(requireRecord(record['compute_drivers'], 'GPU capabilities resource payload.compute_drivers')),
        totalVramGb
    };
    const error = decodeError(record['error'], 'GPU capabilities resource payload.error');
    if (error) decoded.error = error;
    return decoded;
};

const isGpuCapabilitiesResource = (value: JsonValue | null | undefined): value is GpuCapabilitiesResource => {
    return isJsonObject(value) && isBoolean(value['success']) && isJsonObject(value['gpus']) && isJsonObject(value['gpusByDeviceId']) && isJsonObject(value['computeDrivers']) && isFiniteNumber(value['totalVramGb']);
};

const hasGpuEntries = (payload: GpuCapabilitiesResource): boolean => {
    return keys(payload.gpusByDeviceId).length > 0 || keys(payload.gpus).length > 0;
};

const normalizeGpuCapabilitiesResource = (payload: JsonValue | null, context?: Pick<ResourceContext, 'previousValue'>): GpuCapabilitiesResource => {
    const decoded = decodeGpuCapabilitiesResource(payload);
    const previousValue = context?.previousValue ?? null;
    if (!hasGpuEntries(decoded) && isGpuCapabilitiesResource(previousValue) && hasGpuEntries(previousValue)) {
        return previousValue;
    }
    return decoded;
};

export { isGpuCapabilitiesResource, normalizeGpuCapabilitiesResource };
export type { GpuCapabilitiesResource } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
