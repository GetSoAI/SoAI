/* SoAI - Hardware page GPU control validation [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlValidation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuCapabilities, GpuClockCapabilityInfo } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { GpuSettingsUpdatePayload } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

const collectSupportedClockBackend = (backends: Set<string>, info: GpuClockCapabilityInfo | undefined): void => {
    if (info?.supported && typeof info.controlBackend === 'string' && info.controlBackend) {
        backends.add(info.controlBackend);
    }
};

const hasSupportedClockResetBackend = (caps: GpuCapabilities): boolean => {
    const backends = new Set<string>();
    collectSupportedClockBackend(backends, caps.coreClockMhz);
    collectSupportedClockBackend(backends, caps.memClockMhz);
    return backends.size > 0;
};

export const buildGpuResetPayload = (caps: GpuCapabilities | null): GpuSettingsUpdatePayload | null => {
    if (!caps) return null;
    const payload: GpuSettingsUpdatePayload = {};
    if (caps.powerLimitWatts?.supported) payload.powerLimit = 'auto';
    if (caps.fanSpeedPercent?.supported) payload.fanSpeed = 'auto';
    if (hasSupportedClockResetBackend(caps)) {
        payload.resetClocks = true;
    }
    return Object.keys(payload).length ? payload : null;
};

export const hasGpuStorableSettings = (payload: GpuSettingsUpdatePayload): boolean => Object.values(payload).some((value) => value !== true && value !== undefined);
