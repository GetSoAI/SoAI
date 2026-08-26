/* SoAI - Plugins feature GPU binding types [frontend/assets/ts/features/plugins/modals/config/gpuBindingTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';

const PLUGIN_GPU_BINDING_KEY = 'GPU_BINDING';
const PLUGIN_GPU_ALL_ID = 'all';

type PluginGpuBindingMode = 'all' | 'selected';
type PluginGpuBindingBadgeTone = 'neutral' | 'nvidia' | 'amd' | 'intel';

interface PluginGpuBindingEntry {
    id: string;
    label: string;
    badge: string;
    badgeTone: PluginGpuBindingBadgeTone;
    description: string;
    detail: string;
    memoryTotalGb: number;
    haystack: string;
}

interface PluginGpuBindingSelection {
    mode: PluginGpuBindingMode;
    deviceIds: string[];
}

interface PluginGpuBindingSelectorState {
    entries: PluginGpuBindingEntry[];
    selectedIds: string[];
}

const createPluginGpuBindingConfigValue = (selectedIds: Set<string>): JsonObject => {
    const deviceIds = Array.from(selectedIds).filter((id) => id !== PLUGIN_GPU_ALL_ID);
    if (deviceIds.length === 0) {
        return { mode: 'all', deviceIds: [] };
    }
    return { mode: 'selected', deviceIds: deviceIds };
};

export { PLUGIN_GPU_ALL_ID, PLUGIN_GPU_BINDING_KEY, createPluginGpuBindingConfigValue };
export type { PluginGpuBindingBadgeTone, PluginGpuBindingEntry, PluginGpuBindingMode, PluginGpuBindingSelection, PluginGpuBindingSelectorState };
