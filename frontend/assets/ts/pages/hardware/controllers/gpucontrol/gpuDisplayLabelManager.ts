/* SoAI - GPU display label management [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuDisplayLabelManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuCapabilitiesByIndex } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import { resolveHardwareDeviceDisplayName } from '@features/hardware/public.ts';

const str = String;

export const resolveGpuDisplayIndex = (capabilitiesByIndex: GpuCapabilitiesByIndex | null, index: string | number): string => {
    const capabilities = capabilitiesByIndex?.[str(index)] ?? null;
    if (typeof capabilities?.index === 'string' && capabilities.index.trim()) {
        return capabilities.index.trim();
    }
    if (typeof capabilities?.index === 'number' && Number.isFinite(capabilities.index)) {
        return str(capabilities.index);
    }
    throw new Error(`GPU capability index is required for GPU ${str(index)}`);
};

export const resolveGpuDisplayName = (capabilitiesByIndex: GpuCapabilitiesByIndex | null, index: string | number): string => {
    const capabilities = capabilitiesByIndex?.[str(index)] ?? null;
    const displayName = capabilities === null ? null : resolveHardwareDeviceDisplayName(capabilities);
    if (displayName !== null) {
        return displayName;
    }
    throw new Error(`GPU capability name is required for GPU ${str(index)}`);
};
