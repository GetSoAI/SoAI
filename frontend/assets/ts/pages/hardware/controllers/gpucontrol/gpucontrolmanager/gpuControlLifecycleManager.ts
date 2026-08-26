/* SoAI - Hardware page GPU control lifecycle manager [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolmanager/gpuControlLifecycleManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuSettingsState, GpuSnapshot, GpuUiState } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

type TransientActionSync = 'none' | 'render' | 'soaibench';

const clearTransientActions = (state: GpuUiState): void => {
    state.saveMode = false;
    state.showSoAIBenchActions = false;
};

const clearTransientActionsForApplyChange = (state: GpuUiState, canApply: boolean): TransientActionSync => {
    if (!canApply || (!state.saveMode && !state.showSoAIBenchActions)) {
        return 'none';
    }
    const syncType = state.showSoAIBenchActions && !state.saveMode ? 'soaibench' : 'render';
    clearTransientActions(state);
    return syncType;
};

const commitDirectApply = (state: GpuUiState, normalized: GpuSettingsState, snapshot: GpuSnapshot, canStoreAppliedSettings: boolean): void => {
    clearTransientActions(state);
    state.liveSettings = normalized;
    state.previewSlot = null;
    state.previewSettings = null;
    state.previewSource = 'live';
    state.previewHydrated = false;
    state.applyAtBootDesired = false;
    state.bootToggleDirty = false;
    state.canStoreAppliedSettings = canStoreAppliedSettings;
    state.activeSlot = null;
    state.applyCapability = {
        canApply: false,
        mode: 'direct',
        slot: null,
        normalized,
        snapshot
    };
};

const commitSlotApply = (state: GpuUiState, slot: string, boot: boolean | undefined): void => {
    clearTransientActions(state);
    state.previewSlot = slot;
    state.previewSource = 'slot';
    state.previewHydrated = false;
    state.bootToggleDirty = false;
    state.canStoreAppliedSettings = false;
    state.activeSlot = slot;
    if (state.previewSettings) {
        state.liveSettings = state.previewSettings;
    }
    if (boot !== undefined) {
        state.applyAtBootDesired = boot;
        state.bootSlot = boot ? slot : null;
    }
};

const clearSlotSaveMode = (state: GpuUiState): void => {
    const canStoreCurrentSettings = state.canSaveCurrentSettings;
    clearTransientActions(state);
    state.previewSlot = null;
    state.previewSource = 'live';
    state.previewSettings = null;
    state.previewHydrated = false;
    state.bootToggleDirty = false;
    state.canStoreAppliedSettings = canStoreCurrentSettings;
};

const clearSlotPreviewForDirectEdit = (state: GpuUiState): void => {
    state.previewSlot = null;
    state.previewSource = 'live';
    state.previewSettings = null;
    state.previewHydrated = false;
    state.applyAtBootDesired = false;
    state.bootToggleDirty = false;
    state.canStoreAppliedSettings = false;
};

const markGpuSettingsEdited = (state: GpuUiState): void => {
    clearTransientActions(state);
    state.canStoreAppliedSettings = false;
};

export { clearSlotPreviewForDirectEdit, clearSlotSaveMode, clearTransientActions, clearTransientActionsForApplyChange, commitDirectApply, commitSlotApply, markGpuSettingsEdited };
