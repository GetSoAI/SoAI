/* SoAI - GPU primary action controller [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlPrimaryActionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface GpuPrimaryActionState {
    canStoreAppliedSettings: boolean;
    canSaveCurrentSettings: boolean;
    applyCapability: { canApply: boolean } | null;
}

type GpuPrimaryAction = 'apply' | 'save';

const resolveGpuPrimaryAction = (state: GpuPrimaryActionState): GpuPrimaryAction => {
    if (state.canStoreAppliedSettings) {
        return 'save';
    }
    if (state.applyCapability?.canApply) {
        return 'apply';
    }
    return state.canSaveCurrentSettings ? 'save' : 'apply';
};

const hasPendingGpuApplyAction = (state: GpuPrimaryActionState): boolean => {
    return resolveGpuPrimaryAction(state) === 'apply' && !!state.applyCapability?.canApply;
};

export { hasPendingGpuApplyAction, resolveGpuPrimaryAction };
export type { GpuPrimaryAction, GpuPrimaryActionState };
