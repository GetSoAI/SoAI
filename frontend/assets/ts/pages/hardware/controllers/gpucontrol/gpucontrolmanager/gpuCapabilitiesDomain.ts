/* SoAI - Frontend GPU capabilities page lookup projection [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolmanager/gpuCapabilitiesDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuCapabilities, GpuCapabilitiesByIndex, GpuCapabilitiesResource } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import { buildGpuControlKey } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/gpuControlKeyManager.ts';

const addGpuCapabilities = (result: GpuCapabilitiesByIndex, sourceKey: string, capabilities: GpuCapabilities, fallbackDeviceId: string | null): void => {
    const deviceId = capabilities.deviceId ?? fallbackDeviceId;
    const controlKey = buildGpuControlKey(deviceId, sourceKey);
    if (controlKey in result) return;
    result[controlKey] = capabilities.deviceId || !deviceId ? capabilities : { ...capabilities, deviceId };
};

const buildGpuCapabilitiesLookup = (resource: GpuCapabilitiesResource): GpuCapabilitiesByIndex | null => {
    const result: GpuCapabilitiesByIndex = {};
    for (const [deviceId, capabilities] of Object.entries(resource.gpusByDeviceId)) addGpuCapabilities(result, deviceId, capabilities, deviceId);
    for (const [index, capabilities] of Object.entries(resource.gpus)) addGpuCapabilities(result, index, capabilities, null);
    return Object.keys(result).length > 0 ? result : null;
};

export { buildGpuCapabilitiesLookup };
