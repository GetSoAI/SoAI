/* SoAI - Hardware page GPU control manager effects [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolmanager/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeSnapshotForIndex, settingsDiffer } from '@pages/hardware/controllers/gpucontrol/gpuControlNormalization.ts';
import type { GpuCapabilitiesByIndex } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { GpuSettingsState, GpuSnapshot, GpuUiState } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

const str = String;

export const normalizeSliderSnapshotForIndex = (capabilitiesByIndex: GpuCapabilitiesByIndex | null, index: string | number, snapshot: GpuSnapshot): GpuSettingsState => {
    return normalizeSnapshotForIndex(capabilitiesByIndex, index, snapshot);
};

export const computeApplyCapability = (
    capabilitiesByIndex: GpuCapabilitiesByIndex | null,
    index: string | number,
    state: GpuUiState,
    snapshot: GpuSnapshot
): {
    canApply: boolean;
    mode: 'direct' | 'slot';
    slot: string | null;
    normalized: GpuSettingsState;
    snapshot: GpuSnapshot;
    applyAtBoot?: boolean;
} => {
    const normalized = normalizeSliderSnapshotForIndex(capabilitiesByIndex, index, snapshot);
    const match = !!(state.previewSlot && state.previewSettings && !settingsDiffer(normalized, state.previewSettings));

    const mode: 'direct' | 'slot' = match ? 'slot' : 'direct';
    const slot = match ? state.previewSlot : null;
    const diff = settingsDiffer(normalized, state.liveSettings);
    const bootChange = !!(slot && state.bootToggleDirty);

    const canApply = bootChange || (mode === 'slot' ? (slot ? str(state.activeSlot) !== slot : false) : diff);

    const result: {
        canApply: boolean;
        mode: 'direct' | 'slot';
        slot: string | null;
        normalized: GpuSettingsState;
        snapshot: GpuSnapshot;
        applyAtBoot?: boolean;
    } = {
        canApply,
        mode,
        slot,
        normalized,
        snapshot
    };

    if (bootChange) {
        result.applyAtBoot = state.applyAtBootDesired;
    }

    return result;
};
