/* SoAI - GPU primary action controller [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlPrimaryActionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface GpuPrimaryActionState {
    saveMode: boolean;
    canStoreAppliedSettings: boolean;
    canSaveCurrentSettings: boolean;
    applyCapability: { canApply: boolean } | null;
}

type GpuPrimaryAction = 'apply' | 'save';

const resolveGpuPrimaryAction = (state: GpuPrimaryActionState): GpuPrimaryAction => {
    if (state.saveMode || state.canStoreAppliedSettings) {
        return 'save';
    }
    if (state.applyCapability?.canApply) {
        return 'apply';
    }
    return state.canSaveCurrentSettings ? 'save' : 'apply';
};

const hasPendingGpuApplyAction = (state: GpuPrimaryActionState): boolean => {
    return !state.canStoreAppliedSettings && !!state.applyCapability?.canApply;
};

export { hasPendingGpuApplyAction, resolveGpuPrimaryAction };
export type { GpuPrimaryAction, GpuPrimaryActionState };
