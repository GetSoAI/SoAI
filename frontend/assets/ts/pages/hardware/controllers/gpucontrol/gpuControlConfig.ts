/* SoAI - GPU control configuration [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlConfig.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuControlConfig, GpuControlsConfigMap, GpuControlType, GpuSettingKey, GpuSliderConfigItem } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

const freeze = Object.freeze;

export const GPU_CONTROLS_CONFIG: Readonly<GpuControlsConfigMap> = freeze({
    power: {
        type: 'power',
        settingKey: 'powerLimit',
        capabilityKey: 'powerLimitWatts',
        unit: 'W'
    },
    core: {
        type: 'core',
        settingKey: 'coreClock',
        capabilityKey: 'coreClockMhz',
        unit: 'MHz'
    },
    memory: {
        type: 'memory',
        settingKey: 'memClock',
        capabilityKey: 'memClockMhz',
        unit: 'MHz'
    },
    fan: {
        type: 'fan',
        settingKey: 'fanSpeed',
        capabilityKey: 'fanSpeedPercent',
        unit: '%'
    }
} satisfies GpuControlsConfigMap);

export const GPU_CONTROL_TYPES: Readonly<GpuControlType[]> = freeze(Object.values(GPU_CONTROLS_CONFIG).map((candidateValue) => candidateValue.type));

export const GPU_SETTING_KEYS: Readonly<GpuSettingKey[]> = freeze(Object.values(GPU_CONTROLS_CONFIG).map((candidateValue) => candidateValue.settingKey));

export const GPU_PREVIEW_KEY_MAP: Readonly<Record<GpuControlType, GpuSettingKey>> = freeze({
    power: GPU_CONTROLS_CONFIG.power.settingKey,
    core: GPU_CONTROLS_CONFIG.core.settingKey,
    memory: GPU_CONTROLS_CONFIG.memory.settingKey,
    fan: GPU_CONTROLS_CONFIG.fan.settingKey
});

export const GPU_SLIDER_CONFIG: Readonly<GpuSliderConfigItem[]> = freeze(
    GPU_CONTROL_TYPES.map((type) => {
        const config: GpuControlConfig = GPU_CONTROLS_CONFIG[type];
        return {
            type,
            capabilityKey: config.capabilityKey,
            unit: config.unit
        };
    })
);

export const NORMALIZE_KEY_MAP: Readonly<Record<string, GpuSettingKey>> = freeze({
    powerLimit: 'powerLimit',
    fanSpeed: 'fanSpeed',
    coreClock: 'coreClock',
    memClock: 'memClock'
});

export const GPU_SETTING_WIRE_KEYS: Readonly<Record<GpuSettingKey, string>> = freeze({
    powerLimit: 'power_limit',
    fanSpeed: 'fan_speed',
    coreClock: 'core_clock',
    memClock: 'mem_clock'
});
