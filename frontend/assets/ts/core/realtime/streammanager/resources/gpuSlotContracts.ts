/* SoAI - GPU slot realtime V1 contracts [frontend/assets/ts/core/realtime/streammanager/resources/gpuSlotContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuSlotBootState, GpuSlotCurrentSetting, GpuSlotDevice, GpuSlotFieldModes, GpuSlotLiveState, GpuSlotSavedState, GpuSlotSettings } from '@core/types/streamTypes.ts';
import { hasOwn, isBoolean, isNonNegativeInteger, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const requireRecord = (value: JsonValue | undefined, label: string): JsonObject => {
    if (!isJsonObject(value)) throw new TypeError(`${label} must be an object`);
    return value;
};

const requireIsoTimestamp = (value: string, label: string): string => {
    if (!Number.isFinite(new Date(value).getTime())) throw new TypeError(`${label} must be an ISO timestamp`);
    return value;
};

const optionalString = (record: JsonObject, key: string, label: string): string | null | undefined => {
    if (!hasOwn(record, key)) return undefined;
    const value = record[key];
    if (value === null) return null;
    if (!isString(value) || !value.trim()) throw new TypeError(`${label}.${key} must be a non-empty string or null`);
    return value.trim();
};

const decodeSettings = (value: JsonValue | undefined, label: string): GpuSlotSettings => {
    const record = requireRecord(value, label);
    if (hasOwn(record, 'powerLimit') || hasOwn(record, 'coreClock') || hasOwn(record, 'memClock') || hasOwn(record, 'fanSpeed') || hasOwn(record, 'resetClocks')) throw new TypeError(`${label} must use canonical V1 wire fields`);
    const decoded: GpuSlotSettings = {};
    const assignValue = (wireKey: string, domainKey: 'powerLimit' | 'coreClock' | 'memClock' | 'fanSpeed'): void => {
        if (!hasOwn(record, wireKey)) return;
        const setting = record[wireKey];
        if (setting !== null && setting !== 'auto' && (typeof setting !== 'number' || !Number.isFinite(setting))) throw new TypeError(`${label}.${wireKey} is invalid`);
        decoded[domainKey] = setting;
    };
    assignValue('power_limit', 'powerLimit');
    assignValue('core_clock', 'coreClock');
    assignValue('mem_clock', 'memClock');
    assignValue('fan_speed', 'fanSpeed');
    if (hasOwn(record, 'reset_clocks')) {
        if (!isBoolean(record['reset_clocks'])) throw new TypeError(`${label}.reset_clocks must be a boolean`);
        decoded.resetClocks = record['reset_clocks'];
    }
    return decoded;
};

const decodeFieldModes = (value: JsonValue | undefined, label: string): GpuSlotFieldModes => {
    const record = requireRecord(value, label);
    if (hasOwn(record, 'powerLimit') || hasOwn(record, 'coreClock') || hasOwn(record, 'memClock') || hasOwn(record, 'fanSpeed')) throw new TypeError(`${label} must use canonical V1 wire fields`);
    const allowedKeys = new Set(['power_limit', 'core_clock', 'mem_clock', 'fan_speed']);
    if (Object.keys(record).some((key) => !allowedKeys.has(key))) throw new TypeError(`${label} contains an unsupported V1 field`);
    const decoded: GpuSlotFieldModes = {};
    const assignMode = (wireKey: string, domainKey: 'powerLimit' | 'coreClock' | 'memClock' | 'fanSpeed'): void => {
        if (!hasOwn(record, wireKey)) return;
        const mode = record[wireKey];
        if (mode !== 'auto' && mode !== 'manual') throw new TypeError(`${label}.${wireKey} is invalid`);
        decoded[domainKey] = mode;
    };
    assignMode('power_limit', 'powerLimit');
    assignMode('core_clock', 'coreClock');
    assignMode('mem_clock', 'memClock');
    assignMode('fan_speed', 'fanSpeed');
    return decoded;
};

const decodeBoot = (value: JsonValue | undefined, label: string): GpuSlotBootState => {
    const record = requireRecord(value, label);
    if (hasOwn(record, 'appliedSignature') || hasOwn(record, 'appliedAt')) throw new TypeError(`${label} must use canonical V1 wire fields`);
    if (!isBoolean(record['enabled'])) throw new TypeError(`${label}.enabled must be a boolean`);
    if (!hasOwn(record, 'slot') || !hasOwn(record, 'applied_signature') || !hasOwn(record, 'applied_at')) throw new TypeError(`${label} is missing required V1 fields`);
    const appliedAt = optionalString(record, 'applied_at', label);
    return {
        enabled: record['enabled'],
        slot: optionalString(record, 'slot', label) ?? null,
        appliedSignature: optionalString(record, 'applied_signature', label) ?? null,
        appliedAt: appliedAt ? requireIsoTimestamp(appliedAt, `${label}.applied_at`) : null
    };
};

const decodeCurrentSettings = (value: JsonValue | undefined, label: string): Record<string, GpuSlotCurrentSetting> => {
    const record = requireRecord(value, label);
    const decoded: Record<string, GpuSlotCurrentSetting> = {};
    for (const [wireKey, settingValue] of Object.entries(record)) {
        const setting = requireRecord(settingValue, `${label}.${wireKey}`);
        const currentValue = setting['value'];
        if (typeof currentValue !== 'number' || !Number.isFinite(currentValue)) throw new TypeError(`${label}.${wireKey}.value must be finite`);
        const current: GpuSlotCurrentSetting = { value: currentValue };
        if (hasOwn(setting, 'default')) {
            const defaultValue = setting['default'];
            if (typeof defaultValue !== 'number' || !Number.isFinite(defaultValue)) throw new TypeError(`${label}.${wireKey}.default must be finite`);
            current.defaultValue = defaultValue;
        }
        if (hasOwn(setting, 'is_default')) {
            if (!isBoolean(setting['is_default'])) throw new TypeError(`${label}.${wireKey}.is_default must be a boolean`);
            current.isDefault = setting['is_default'];
        }
        const domainKey = wireKey === 'power_limit' ? 'powerLimit' : wireKey === 'core_clock' ? 'coreClock' : wireKey === 'mem_clock' ? 'memClock' : wireKey === 'fan_speed' ? 'fanSpeed' : null;
        if (domainKey === null) throw new TypeError(`${label}.${wireKey} is not a V1 GPU setting`);
        decoded[domainKey] = current;
    }
    return decoded;
};

const decodeLive = (value: JsonValue | undefined, label: string): GpuSlotLiveState => {
    const record = requireRecord(value, label);
    if (hasOwn(record, 'deviceId') || hasOwn(record, 'currentSettings') || hasOwn(record, 'bootState') || hasOwn(record, 'activeSlot')) throw new TypeError(`${label} must use canonical V1 wire fields`);
    const deviceId = record['device_id'];
    if (!isString(deviceId) || !deviceId.trim()) throw new TypeError(`${label}.device_id must be a non-empty string`);
    const bootState = decodeBoot(record['boot_state'], `${label}.boot_state`);
    if (!isBoolean(record['boot_enabled'])) throw new TypeError(`${label}.boot_enabled must be a boolean`);
    return {
        deviceId: deviceId.trim(),
        currentSettings: decodeCurrentSettings(record['current_settings'], `${label}.current_settings`),
        bootState,
        bootEnabled: record['boot_enabled'],
        bootSlot: optionalString(record, 'boot_slot', label) ?? null,
        activeSlot: optionalString(record, 'active_slot', label) ?? null,
        activeSignature: optionalString(record, 'active_signature', label) ?? null,
        activeAppliedAt: optionalString(record, 'active_applied_at', label) ?? null
    };
};

const decodeSlots = (value: JsonValue | undefined, label: string): Record<string, GpuSlotSavedState> => {
    const record = requireRecord(value, label);
    const decoded: Record<string, GpuSlotSavedState> = {};
    for (const [slotId, slotValue] of Object.entries(record)) {
        const slot = requireRecord(slotValue, `${label}.${slotId}`);
        if (hasOwn(slot, 'fieldModes') || hasOwn(slot, 'savedAt') || hasOwn(slot, 'lastAppliedAt')) throw new TypeError(`${label}.${slotId} must use canonical V1 wire fields`);
        const saved: GpuSlotSavedState = { settings: decodeSettings(slot['settings'], `${label}.${slotId}.settings`), fieldModes: decodeFieldModes(slot['field_modes'], `${label}.${slotId}.field_modes`) };
        if (!hasOwn(slot, 'saved_at') || !hasOwn(slot, 'last_applied_at') || !hasOwn(slot, 'signature')) throw new TypeError(`${label}.${slotId} is missing required V1 fields`);
        const savedAt = optionalString(slot, 'saved_at', `${label}.${slotId}`);
        const lastAppliedAt = optionalString(slot, 'last_applied_at', `${label}.${slotId}`);
        const signature = optionalString(slot, 'signature', `${label}.${slotId}`);
        if (!savedAt) throw new TypeError(`${label}.${slotId}.saved_at must be a non-empty string`);
        if (!signature) throw new TypeError(`${label}.${slotId}.signature must be a non-empty string`);
        saved.savedAt = requireIsoTimestamp(savedAt, `${label}.${slotId}.saved_at`);
        saved.lastAppliedAt = lastAppliedAt ? requireIsoTimestamp(lastAppliedAt, `${label}.${slotId}.last_applied_at`) : null;
        saved.signature = signature;
        decoded[slotId] = saved;
    }
    return decoded;
};

const decodeGpuSlotDevice = (deviceId: string, value: JsonValue, label: string): GpuSlotDevice => {
    const record = requireRecord(value, label);
    if (hasOwn(record, 'gpuIndex')) throw new TypeError(`${label} must use canonical V1 wire fields`);
    const gpuIndex = record['gpu_index'];
    if (gpuIndex !== null && gpuIndex !== undefined && !isNonNegativeInteger(gpuIndex)) throw new TypeError(`${label}.gpu_index must be a non-negative integer or null`);
    const name = record['name'];
    if (name !== null && name !== undefined && !isString(name)) throw new TypeError(`${label}.name must be a string or null`);
    const decoded: GpuSlotDevice = { deviceId, name: isString(name) ? name : null, gpuIndex: isNonNegativeInteger(gpuIndex) ? gpuIndex : null, slots: decodeSlots(record['slots'], `${label}.slots`), boot: decodeBoot(record['boot'], `${label}.boot`), live: decodeLive(record['live'], `${label}.live`) };
    if (hasOwn(record, 'field_modes')) decoded.fieldModes = decodeFieldModes(record['field_modes'], `${label}.field_modes`);
    if (hasOwn(record, 'applied_settings')) decoded.appliedSettings = decodeSettings(record['applied_settings'], `${label}.applied_settings`);
    return decoded;
};

export { decodeBoot, decodeGpuSlotDevice, decodeLive, decodeSlots };
