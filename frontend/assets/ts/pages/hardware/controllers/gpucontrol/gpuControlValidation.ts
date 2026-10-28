/* SoAI - Hardware page GPU control validation [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlValidation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuCapabilities } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import { GPU_CONTROLS_CONFIG, GPU_SLIDER_CONFIG } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';
import { isGpuCapabilityActionable } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/guards.ts';
import type { GpuSettingsState, GpuSettingsUpdatePayload } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

export const buildGpuResetPayload = (caps: GpuCapabilities | null, live: GpuSettingsState | null): GpuSettingsUpdatePayload | null => {
    if (!caps || !live) return null;
    const payload: GpuSettingsUpdatePayload = {};
    for (const { capabilityKey, type } of GPU_SLIDER_CONFIG) {
        const settingKey = GPU_CONTROLS_CONFIG[type].settingKey;
        const requiresReset = live[settingKey].mode !== 'auto';
        if (isGpuCapabilityActionable(caps[capabilityKey], 'auto') && requiresReset) payload[settingKey] = 'auto';
    }
    return Object.keys(payload).length ? payload : null;
};

export const hasGpuResettableSettings = (caps: GpuCapabilities | null, live: GpuSettingsState | null, draft: GpuSettingsState | null = null): boolean => buildGpuResetPayload(caps, live) !== null || buildGpuResetPayload(caps, draft) !== null;

export const hasGpuStorableSettings = (payload: GpuSettingsUpdatePayload): boolean => Object.values(payload).some((value) => value !== true && value !== undefined);
