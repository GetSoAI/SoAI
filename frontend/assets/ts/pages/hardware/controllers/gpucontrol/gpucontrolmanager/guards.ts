/* SoAI - Hardware page GPU control manager validation [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolmanager/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isObject } from '@core/typeGuards.ts';
import { GPU_CONTROLS_CONFIG } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';
import type { GpuCapabilities, GpuCapabilitiesByIndex, GpuCapabilityControlInfo, GpuClockCapabilityInfo } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { GpuControlType, GpuSettingKey } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

type GpuCapabilityActionableCandidate = GpuCapabilityControlInfo | GpuClockCapabilityInfo;

const CONTROL_TYPE_BY_SETTING_KEY: Record<GpuSettingKey, GpuControlType> = {
    powerLimit: 'power',
    coreClock: 'core',
    memClock: 'memory',
    fanSpeed: 'fan'
};

export const isGpuControlType = (value: JsonValue): value is GpuControlType => {
    return value === 'power' || value === 'core' || value === 'memory' || value === 'fan';
};

export const isGpuCapabilityActionable = (value: GpuCapabilityActionableCandidate | null | undefined): boolean => {
    if (!isObject(value)) {
        return false;
    }
    const controlBackend = value.controlBackend;
    return value.supported === true && typeof controlBackend === 'string' && controlBackend.trim().length > 0;
};

export const hasActionableGpuControls = (capabilities: GpuCapabilities | null | undefined): boolean => {
    return !!capabilities && (isGpuCapabilityActionable(capabilities.powerLimitWatts) || isGpuCapabilityActionable(capabilities.coreClockMhz) || isGpuCapabilityActionable(capabilities.memClockMhz) || isGpuCapabilityActionable(capabilities.fanSpeedPercent));
};

export const hasAnyActionableGpuControls = (capabilitiesByIndex: GpuCapabilitiesByIndex | null): boolean => {
    return !!capabilitiesByIndex && Object.values(capabilitiesByIndex).some((capabilities) => hasActionableGpuControls(capabilities));
};

export const isControlSupported = (capabilitiesByIndex: GpuCapabilitiesByIndex | null, index: string | number, type: string): boolean => {
    if (!isGpuControlType(type)) {
        return false;
    }

    const capabilityKey = GPU_CONTROLS_CONFIG[type].capabilityKey;
    if (!capabilityKey) {
        return false;
    }

    const caps = capabilitiesByIndex?.[String(index)];
    const info = caps?.[capabilityKey];
    if (!info || !isObject(info)) {
        return false;
    }

    return isGpuCapabilityActionable(info);
};

export const isGpuSettingSupported = (capabilitiesByIndex: GpuCapabilitiesByIndex | null, index: string | number, key: GpuSettingKey): boolean => {
    return isControlSupported(capabilitiesByIndex, index, CONTROL_TYPE_BY_SETTING_KEY[key]);
};
