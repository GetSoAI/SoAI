/* SoAI - Frontend GPU capabilities realtime V1 contracts [frontend/assets/ts/core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import { toJsonCompatibleObject } from '@core/primitives/clone.ts';
import { hasOwn, isBoolean, isFiniteNumber, isString } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';

type GpuCapabilityError = JsonObject & {
    code: string;
    message: string;
    details?: OpaqueJsonObject;
};

type GpuCurrentSetting = JsonObject & {
    value: number;
    defaultValue?: number;
    isDefault?: boolean;
};

type GpuCurrentSettings = JsonObject & {
    powerLimit?: GpuCurrentSetting;
    coreClock?: GpuCurrentSetting;
    memClock?: GpuCurrentSetting;
    fanSpeed?: GpuCurrentSetting;
};

type GpuCapabilityControlInfo = JsonObject & {
    supported?: boolean;
    min?: number;
    max?: number;
    step?: number;
    default?: number;
    current?: number;
    value?: number;
    ticks?: number;
    minimum?: number;
    maximum?: number;
    unit?: string;
    mode?: 'auto' | 'manual';
    controlBackend?: string | null;
    requiresAdmin?: boolean;
    unsupportedReason?: string | null;
    error?: GpuCapabilityError | null;
};

type GpuClockCapabilityInfo = GpuCapabilityControlInfo & {
    levels?: Array<JsonObject & { level: number; mhz: number }>;
    allowedValues?: number[];
    offsetMin?: number;
    offsetMax?: number;
};

type GpuCapabilities = JsonObject & {
    index?: number | string;
    deviceId?: string;
    vendor?: string;
    vendorId?: number;
    pciBdf?: string | null;
    os?: string;
    driver?: string | null;
    controlBackends?: string[];
    type?: string;
    powerLimitWatts?: GpuCapabilityControlInfo;
    coreClockMhz?: GpuClockCapabilityInfo;
    memClockMhz?: GpuClockCapabilityInfo;
    fanSpeedPercent?: GpuCapabilityControlInfo;
    name?: string;
    displayName?: string;
    activeSlot?: string | null;
    bootSlot?: string | null;
    live?: JsonObject & {
        activeSlot?: string | null;
        bootSlot?: string | null;
        currentSettings: GpuCurrentSettings;
    };
    currentSettings?: GpuCurrentSettings;
};

type GpuCapabilitiesResource = JsonObject & {
    success: boolean;
    gpus: Record<string, GpuCapabilities> & JsonObject;
    gpusByDeviceId: Record<string, GpuCapabilities> & JsonObject;
    computeDrivers: OpaqueJsonObject;
    totalVramGb: number;
    error?: GpuCapabilityError;
};

type GpuCapabilitiesByIndex = Record<string, GpuCapabilities>;

const optionalNumber = (record: JsonObject, key: string, label: string): number | undefined => {
    const value = record[key];
    if (value === undefined || value === null) return undefined;
    if (!isFiniteNumber(value)) throw new TypeError(`${label}.${key} must be a finite number`);
    return value;
};

const optionalText = (record: JsonObject, key: string, label: string): string | null | undefined => {
    if (!hasOwn(record, key)) return undefined;
    const value = record[key];
    if (value === null) return null;
    if (!isString(value)) throw new TypeError(`${label}.${key} must be a string or null`);
    return value;
};

const decodeError = (value: JsonValue | undefined, label: string): GpuCapabilityError | null | undefined => {
    if (value === undefined) return undefined;
    if (value === null) return null;
    const record = requireRecord(value, label);
    const code = record['code'];
    const message = record['message'];
    if (!isString(code) || !code.trim()) throw new TypeError(`${label}.code must be a non-empty string`);
    if (!isString(message) || !message.trim()) throw new TypeError(`${label}.message must be a non-empty string`);
    const error: GpuCapabilityError = { code, message };
    if (record['details'] !== undefined && record['details'] !== null) error.details = toJsonCompatibleObject(requireRecord(record['details'], `${label}.details`));
    return error;
};

const decodeCurrentSetting = (value: JsonValue | undefined, label: string): GpuCurrentSetting | undefined => {
    if (value === undefined || value === null) return undefined;
    const record = requireRecord(value, label);
    if (hasOwn(record, 'defaultValue') || hasOwn(record, 'isDefault')) throw new TypeError(`${label} must use canonical V1 wire fields`);
    const settingValue = optionalNumber(record, 'value', label);
    if (settingValue === undefined) throw new TypeError(`${label}.value must be a finite number`);
    const setting: GpuCurrentSetting = { value: settingValue };
    const defaultValue = optionalNumber(record, 'default', label);
    if (defaultValue !== undefined) setting.defaultValue = defaultValue;
    const isDefault = record['is_default'];
    if (isDefault !== undefined) {
        if (!isBoolean(isDefault)) throw new TypeError(`${label}.is_default must be a boolean`);
        setting.isDefault = isDefault;
    }
    return setting;
};

const decodeCurrentSettings = (value: JsonValue | undefined, label: string): GpuCurrentSettings => {
    if (value === undefined || value === null) return {};
    const record = requireRecord(value, label);
    if (hasOwn(record, 'powerLimit') || hasOwn(record, 'coreClock')) throw new TypeError(`${label} must use canonical V1 wire fields`);
    const settings: GpuCurrentSettings = {};
    const powerLimit = decodeCurrentSetting(record['power_limit'], `${label}.power_limit`);
    const coreClock = decodeCurrentSetting(record['core_clock'], `${label}.core_clock`);
    const memClock = decodeCurrentSetting(record['mem_clock'], `${label}.mem_clock`);
    const fanSpeed = decodeCurrentSetting(record['fan_speed'], `${label}.fan_speed`);
    if (powerLimit) settings.powerLimit = powerLimit;
    if (coreClock) settings.coreClock = coreClock;
    if (memClock) settings.memClock = memClock;
    if (fanSpeed) settings.fanSpeed = fanSpeed;
    return settings;
};

const assignCapabilityNumbers = (record: JsonObject, capability: GpuCapabilityControlInfo, label: string): void => {
    const min = optionalNumber(record, 'min', label);
    const max = optionalNumber(record, 'max', label);
    const step = optionalNumber(record, 'step', label);
    const defaultValue = optionalNumber(record, 'default', label);
    const current = optionalNumber(record, 'current', label);
    const value = optionalNumber(record, 'value', label);
    const ticks = optionalNumber(record, 'ticks', label);
    const minimum = optionalNumber(record, 'minimum', label);
    const maximum = optionalNumber(record, 'maximum', label);
    if (min !== undefined) capability.min = min;
    if (max !== undefined) capability.max = max;
    if (step !== undefined) capability.step = step;
    if (defaultValue !== undefined) capability.default = defaultValue;
    if (current !== undefined) capability.current = current;
    if (value !== undefined) capability.value = value;
    if (ticks !== undefined) capability.ticks = ticks;
    if (minimum !== undefined) capability.minimum = minimum;
    if (maximum !== undefined) capability.maximum = maximum;
};

const decodeControlCapability = (value: JsonValue | undefined, label: string): GpuCapabilityControlInfo | undefined => {
    if (value === undefined || value === null) return undefined;
    const record = requireRecord(value, label);
    if (hasOwn(record, 'controlBackend') || hasOwn(record, 'requiresAdmin') || hasOwn(record, 'unsupportedReason')) throw new TypeError(`${label} must use canonical V1 wire fields`);
    const capability: GpuCapabilityControlInfo = {};
    if (record['supported'] !== undefined) {
        if (!isBoolean(record['supported'])) throw new TypeError(`${label}.supported must be a boolean`);
        capability.supported = record['supported'];
    }
    assignCapabilityNumbers(record, capability, label);
    const unit = optionalText(record, 'unit', label);
    if (unit !== undefined && unit !== null) capability.unit = unit;
    const mode = record['mode'];
    if (mode !== undefined) {
        if (mode !== 'auto' && mode !== 'manual') throw new TypeError(`${label}.mode must be auto or manual`);
        capability.mode = mode;
    }
    const controlBackend = optionalText(record, 'control_backend', label);
    const unsupportedReason = optionalText(record, 'unsupported_reason', label);
    if (controlBackend !== undefined) capability.controlBackend = controlBackend;
    if (unsupportedReason !== undefined) capability.unsupportedReason = unsupportedReason;
    if (record['requires_admin'] !== undefined) {
        if (!isBoolean(record['requires_admin'])) throw new TypeError(`${label}.requires_admin must be a boolean`);
        capability.requiresAdmin = record['requires_admin'];
    }
    const error = decodeError(record['error'], `${label}.error`);
    if (error !== undefined) capability.error = error;
    return capability;
};

const decodeClockCapability = (value: JsonValue | undefined, label: string): GpuClockCapabilityInfo | undefined => {
    const capability = decodeControlCapability(value, label);
    if (!capability || value === undefined || value === null) return capability;
    const clock: GpuClockCapabilityInfo = capability;
    const record = requireRecord(value, label);
    const offsetMin = optionalNumber(record, 'offset_min', label);
    const offsetMax = optionalNumber(record, 'offset_max', label);
    if (offsetMin !== undefined) clock.offsetMin = offsetMin;
    if (offsetMax !== undefined) clock.offsetMax = offsetMax;
    if (record['allowed_values'] !== undefined) {
        if (!Array.isArray(record['allowed_values']) || !record['allowed_values'].every(isFiniteNumber)) throw new TypeError(`${label}.allowed_values must be a finite number array`);
        clock.allowedValues = [...record['allowed_values']];
    }
    if (record['levels'] !== undefined) {
        if (!Array.isArray(record['levels'])) throw new TypeError(`${label}.levels must be an array`);
        clock.levels = record['levels'].map((entry, index) => {
            const levelRecord = requireRecord(entry, `${label}.levels[${String(index)}]`);
            const level = optionalNumber(levelRecord, 'level', `${label}.levels[${String(index)}]`);
            const mhz = optionalNumber(levelRecord, 'mhz', `${label}.levels[${String(index)}]`);
            if (level === undefined || mhz === undefined) throw new TypeError(`${label}.levels entries require level and mhz`);
            return { level, mhz };
        });
    }
    return clock;
};

export type { GpuCapabilities, GpuCapabilitiesByIndex, GpuCapabilitiesResource, GpuCapabilityControlInfo, GpuClockCapabilityInfo, GpuCurrentSettings };
export { decodeClockCapability, decodeControlCapability, decodeCurrentSettings, decodeError, optionalNumber, optionalText };
