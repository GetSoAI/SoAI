/* SoAI - Hardware page GPU control normalization [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlNormalization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { readCoercedFiniteNumberOrNullValue } from '@core/types/numberCoercionReaders.ts';
import { isFiniteNumber, isNullOrUndefined, isObject } from '@core/typeGuards.ts';
import { GPU_SETTING_KEYS, NORMALIZE_KEY_MAP } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';
import type { GpuCapabilities, GpuCapabilitiesByIndex } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { ChartOhlcNumeric, GpuControlType, GpuControlValue, GpuFieldMode, GpuSettingsState, GpuSettingState, GpuSlotEntry, GpuSnapshot, OffsetControlContext } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

const entries = Object.entries;

const createSettingState = (mode: GpuFieldMode, value: number | null = null): GpuSettingState => ({
    mode,
    value: isFiniteNumber(value) ? value : null
});

export const createDefaultSettingsState = (): GpuSettingsState => ({
    powerLimit: createSettingState('auto'),
    fanSpeed: createSettingState('auto'),
    coreClock: createSettingState('auto'),
    memClock: createSettingState('auto')
});

export const normalizeGpuValue = (value: JsonValue): GpuControlValue => {
    const numeric = readCoercedFiniteNumberOrNullValue(value);
    return numeric === null ? 'auto' : numeric;
};

export const normalizeFieldMode = (value: JsonValue): GpuFieldMode | null => {
    if (value !== 'auto' && value !== 'manual') {
        return null;
    }
    return value;
};

export const settingStateToValue = (state: GpuSettingState | null | undefined): GpuControlValue => {
    if (!state || state.mode === 'auto' || !isFiniteNumber(state.value)) {
        return 'auto';
    }
    return state.value;
};

export const getOffsetControlContext = (capabilitiesByIndex: GpuCapabilitiesByIndex | null, index: string | number, controlType: GpuControlType): OffsetControlContext | null => {
    const key = String(index);
    const caps = capabilitiesByIndex?.[key];
    if (!caps) return null;

    const createAbsoluteRangeInfo = (raw: { min?: number; max?: number; minimum?: number; maximum?: number; default?: number }): { min?: number; max?: number; default?: number } => {
        const info: { min?: number; max?: number; default?: number } = {};

        if (typeof raw.min === 'number') info.min = raw.min;
        else if (typeof raw.minimum === 'number') info.min = raw.minimum;

        if (typeof raw.max === 'number') info.max = raw.max;
        else if (typeof raw.maximum === 'number') info.max = raw.maximum;

        if (typeof raw.default === 'number') info.default = raw.default;

        return info;
    };

    const computeFromAbsoluteRange = (info: { min?: number; max?: number; default?: number } | null): OffsetControlContext | null => {
        if (!info) return null;
        const min = Number(info.min);
        const max = Number(info.max);
        const def = Number(info.default);
        if (![min, max, def].every(isFiniteNumber)) return null;
        const offsetMin = min - def;
        const offsetMax = max - def;
        if (!isFiniteNumber(offsetMin) || !isFiniteNumber(offsetMax) || offsetMin >= offsetMax) return null;
        return { defaultAbs: def, offsetMin, offsetMax };
    };

    if (controlType === 'power') {
        const powerCaps = caps.powerLimitWatts;
        if (!powerCaps || powerCaps.supported !== true) return null;
        return computeFromAbsoluteRange(createAbsoluteRangeInfo(powerCaps));
    }

    if (controlType !== 'core' && controlType !== 'memory') {
        return null;
    }

    const clockCaps = controlType === 'core' ? caps.coreClockMhz : caps.memClockMhz;
    if (!clockCaps || clockCaps.supported !== true) return null;

    if (caps.type === 'nvidia') {
        const def = Number(clockCaps.default);
        const offsetMin = Number(clockCaps.offsetMin);
        const offsetMax = Number(clockCaps.offsetMax);
        if (![def, offsetMin, offsetMax].every(isFiniteNumber)) return null;
        if (offsetMin >= offsetMax) return null;
        return { defaultAbs: def, offsetMin, offsetMax };
    }

    return computeFromAbsoluteRange(createAbsoluteRangeInfo(clockCaps));
};

const resolveSettingsInfoFromSources = (caps: GpuCapabilities | null, slotEntry: GpuSlotEntry | null): Record<string, JsonValue> => {
    const slotLive = slotEntry?.live;
    const capsLive = caps?.live;
    const liveSettings = isObject(capsLive?.currentSettings) ? capsLive?.currentSettings : null;
    const slotSettings = isObject(slotLive?.currentSettings) ? slotLive?.currentSettings : null;
    return slotSettings ?? liveSettings ?? {};
};

export const normalizeLiveSettings = (chartOhlc: ChartOhlcNumeric, caps: GpuCapabilities | null, slotEntry: GpuSlotEntry | null): GpuSettingsState => {
    const settingsInfo = resolveSettingsInfoFromSources(caps, slotEntry);
    const result = createDefaultSettingsState();
    GPU_SETTING_KEYS.forEach((settingKey) => {
        const raw = settingsInfo[settingKey];
        const entry = isObject(raw) ? raw : {};
        const resolved = chartOhlc.resolveNumeric(entry['value'] ?? null, entry['defaultValue'] ?? null);
        if (entry['isDefault'] === true) {
            result[settingKey] = createSettingState('auto', resolved);
            return;
        }
        result[settingKey] = createSettingState(isFiniteNumber(resolved) ? 'manual' : 'auto', resolved);
    });
    return result;
};

export const normalizeSlotSettings = (rawSettings: Record<string, JsonValue>, rawFieldModes: Record<string, JsonValue> | null = null): GpuSettingsState => {
    const result = createDefaultSettingsState();
    if (!isObject(rawSettings)) return result;
    entries(rawSettings).forEach(([key, value]) => {
        const normalizedKey = NORMALIZE_KEY_MAP[key];
        if (!normalizedKey) return;
        const normalizedValue = normalizeGpuValue(value);
        if (normalizedValue === 'auto') {
            result[normalizedKey] = createSettingState('auto');
            return;
        }
        const rawMode = rawFieldModes ? normalizeFieldMode(rawFieldModes[key] ?? rawFieldModes[normalizedKey] ?? null) : null;
        result[normalizedKey] = createSettingState(rawMode === 'auto' ? 'auto' : 'manual', normalizedValue);
    });
    return result;
};

export const normalizeSnapshot = (snapshot: GpuSnapshot): GpuSettingsState => ({
    powerLimit: createSettingState(snapshot.power.mode, snapshot.power.value),
    fanSpeed: createSettingState(snapshot.fan.mode, snapshot.fan.value),
    coreClock: createSettingState(snapshot.core.mode, snapshot.core.value),
    memClock: createSettingState(snapshot.memory.mode, snapshot.memory.value)
});

export const normalizeSnapshotForIndex = (capabilitiesByIndex: GpuCapabilitiesByIndex | null, index: string | number, snapshot: GpuSnapshot): GpuSettingsState => {
    const base = normalizeSnapshot(snapshot);

    const convertOffsetToAbsolute = (state: GpuSettingState, context: OffsetControlContext | null): GpuSettingState => {
        if (!context || state.mode === 'auto' || !isFiniteNumber(state.value)) return state;
        let bounded = state.value;
        if (bounded < context.offsetMin) bounded = context.offsetMin;
        if (bounded > context.offsetMax) bounded = context.offsetMax;
        return createSettingState('manual', context.defaultAbs + bounded);
    };

    return {
        powerLimit: convertOffsetToAbsolute(base.powerLimit, getOffsetControlContext(capabilitiesByIndex, index, 'power')),
        fanSpeed: base.fanSpeed,
        coreClock: convertOffsetToAbsolute(base.coreClock, getOffsetControlContext(capabilitiesByIndex, index, 'core')),
        memClock: convertOffsetToAbsolute(base.memClock, getOffsetControlContext(capabilitiesByIndex, index, 'memory'))
    };
};

export const gpuSettingStatesEqual = (left: GpuSettingState, right: GpuSettingState): boolean => {
    if (left.mode !== right.mode) {
        return false;
    }
    if (left.mode === 'auto') {
        return true;
    }
    return isFiniteNumber(left.value) && isFiniteNumber(right.value) && left.value === right.value;
};

export const settingsEqual = (left: GpuSettingsState | null, right: GpuSettingsState | null): boolean => {
    if (!left || !right) return false;
    return GPU_SETTING_KEYS.every((settingKey) => gpuSettingStatesEqual(left[settingKey], right[settingKey]));
};

export const settingsDiffer = (left: GpuSettingsState | null, right: GpuSettingsState | null): boolean => !settingsEqual(left, right);

export const slotExists = (slotId: string, entry: GpuSlotEntry | null): boolean => {
    if (!slotId || !entry?.slots) return false;
    return !!entry.slots[String(slotId)];
};

export const normalizeSlotId = (slotValue: JsonValue): string | null => (isNullOrUndefined(slotValue) ? null : String(slotValue));
