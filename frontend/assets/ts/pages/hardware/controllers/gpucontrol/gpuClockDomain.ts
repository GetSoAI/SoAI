/* SoAI - Hardware page selectable clock domains [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuClockDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuClockCapabilityInfo } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';

type ClockDomain = { type: 'continuous' } | { type: 'discrete'; values: readonly number[] } | { type: 'invalid' };

export const resolveClockDomain = (capability: GpuClockCapabilityInfo): ClockDomain => {
    if (capability.controlBackend === 'amd_overdrive') {
        if (capability.allowedValues?.length || capability.clockControlType) return { type: 'invalid' };
        return { type: 'continuous' };
    }
    if (capability.levels?.length) return { type: 'discrete', values: capability.levels.map((entry) => entry.mhz) };
    if (capability.allowedValues?.length) return { type: 'discrete', values: capability.allowedValues };
    return { type: 'continuous' };
};
