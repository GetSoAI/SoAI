/* SoAI - Hardware page GPU control manager state [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpucontrolmanager/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuUiState } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';
import { hasPendingGpuApplyAction } from '@pages/hardware/controllers/gpucontrol/gpuControlPrimaryActionController.ts';

const str = String;

export const hasUnsavedGpuChanges = (states: Map<string, GpuUiState>): boolean => {
    for (const state of states.values()) {
        if (state && hasPendingGpuApplyAction(state)) {
            return true;
        }
    }
    return false;
};

export const findFirstPendingGpuIndex = (states: Map<string, GpuUiState>): string | null => {
    for (const [index, state] of states.entries()) {
        if (state && hasPendingGpuApplyAction(state)) {
            return index;
        }
    }
    return null;
};

export const hasActiveGpuSaveMode = (states: Map<string, GpuUiState>): boolean => {
    return Array.from(states.values()).some((state) => state?.saveMode);
};

export const cancelAllGpuSaveModes = (states: Map<string, GpuUiState>, rerender: (indices: string[]) => void): void => {
    const updated: string[] = [];

    states.forEach((state, key) => {
        if (!state?.saveMode) {
            return;
        }

        state.saveMode = false;
        state.bootToggleDirty = false;
        updated.push(str(key));
    });

    if (updated.length) {
        rerender(updated);
    }
};

export const setGpuSaveMode = (ensureUiState: (index: string | number) => GpuUiState, index: string | number, enabled: boolean, rerender: (index: string) => void): void => {
    const key = str(index);
    const state = ensureUiState(key);
    const next = !!enabled;

    if (state.saveMode === next) {
        return;
    }

    state.saveMode = next;
    if (!next) {
        state.bootToggleDirty = false;
    }
    rerender(key);
};
