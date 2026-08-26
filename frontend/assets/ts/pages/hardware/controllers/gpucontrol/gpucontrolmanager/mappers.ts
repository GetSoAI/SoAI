/* SoAI - GPU control manager mapping [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolmanager/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuSlotDevice, GpuSlotsBuilderResult } from '@core/types/streamTypes.ts';
import { collectGpuControlLookupKeys } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/gpuControlKeyManager.ts';
import type { GpuSavedSettingsState } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

const assignSlotEntryAlias = (byIndex: Record<string, GpuSlotDevice>, lookupKey: string, entry: GpuSlotDevice): void => {
    if (!byIndex[lookupKey]) {
        byIndex[lookupKey] = entry;
    }
};
export const parseSavedSettingsState = (value: GpuSlotsBuilderResult | null): GpuSavedSettingsState | null => {
    if (!value) return null;
    const byIndex: Record<string, GpuSlotDevice> = {};
    Object.entries(value.byDeviceId).forEach(([deviceId, entry]) => {
        collectGpuControlLookupKeys({ deviceId, sourceKey: deviceId, gpuIndex: entry.gpuIndex }).forEach((lookupKey) => {
            assignSlotEntryAlias(byIndex, lookupKey, entry);
        });
    });
    return Object.keys(byIndex).length ? { byIndex } : null;
};
