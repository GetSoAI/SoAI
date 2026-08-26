/* SoAI - Hardware page GPU control state [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuUiState } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

export const createDefaultGpuUiState = (): GpuUiState => ({
    deviceId: null,
    saveMode: false,
    previewSlot: null,
    previewSettings: null,
    previewSource: 'live',
    previewHydrated: false,
    applyAtBootDesired: false,
    bootToggleDirty: false,
    canStoreAppliedSettings: false,
    canSaveCurrentSettings: false,
    showSoAIBenchActions: false,
    soaibenchStopRequested: false,
    activeSlot: null,
    bootSlot: null,
    liveSettings: null,
    slotMetadata: null,
    pending: false,
    applyCapability: null,
    initialized: false
});

export class GpuControlUiStateStore {
    readonly states: Map<string, GpuUiState> = new Map();

    ensure(index: string | number): GpuUiState {
        const key = String(index);
        const existing = this.states.get(key);
        if (existing) return existing;
        const created = createDefaultGpuUiState();
        this.states.set(key, created);
        return created;
    }

    clear(): void {
        this.states.clear();
    }
}
