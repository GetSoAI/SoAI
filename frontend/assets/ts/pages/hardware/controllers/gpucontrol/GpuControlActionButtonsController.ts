/* SoAI - Hardware page GPU control action buttons controller [frontend/assets/ts/pages/hardware/controllers/gpucontrol/GpuControlActionButtonsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { setLoadingButtonState } from '@core/ui/loadingbuttons/service.ts';
import { type GpuPrimaryAction, hasPendingGpuApplyAction } from '@pages/hardware/controllers/gpucontrol/gpuControlPrimaryActionController.ts';
import type { GpuSnapshot } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

interface SyncGpuControlActionButtonsInput {
    index: string;
    snapshot: GpuSnapshot;
    pending: boolean;
    saveMode: boolean;
    canStoreAppliedSettings: boolean;
    canSaveCurrentSettings: boolean;
    applyCapability: { canApply: boolean } | null;
    activeSlot: string | null;
    previewSlot: string | null;
    bootSlot: string | null;
}

const setButtonDisabledState = (button: HTMLButtonElement, disabled: boolean): void => {
    button.disabled = disabled;
    button.setAttribute('aria-disabled', String(disabled));
};

const resolveIndexedButton = (className: string, index: string): HTMLButtonElement | null => {
    for (const element of dom.resolveAll(`.${className}`)) {
        if (element instanceof HTMLButtonElement && element.dataset['gpuIndex'] === index) {
            return element;
        }
    }
    return null;
};

const resolveIndexedButtons = (className: string, index: string): HTMLButtonElement[] => {
    return dom.resolveAll(`.${className}`).filter((element): element is HTMLButtonElement => element instanceof HTMLButtonElement && element.dataset['gpuIndex'] === index);
};

const hasMountedGpuControlPanel = (index: string): boolean => {
    for (const element of dom.resolveAll('.gpu-control-panel')) {
        if (element instanceof HTMLElement && element.dataset['gpuIndex'] === index) {
            return true;
        }
    }
    return false;
};

const requiresGpuPrimaryActionRender = (index: string, primaryAction: GpuPrimaryAction): boolean => {
    if (!hasMountedGpuControlPanel(index)) {
        return false;
    }
    const saveButton = resolveIndexedButton('gpu-save-btn', index);
    const applyButton = resolveIndexedButton('gpu-apply-btn', index);
    return primaryAction === 'save' ? !saveButton : !applyButton;
};

const hasManualSnapshotControl = (snapshot: GpuSnapshot): boolean => {
    return snapshot.power.mode === 'manual' || snapshot.core.mode === 'manual' || snapshot.memory.mode === 'manual' || snapshot.fan.mode === 'manual';
};

export const GpuControlActionButtonsController = (input: SyncGpuControlActionButtonsInput): void => {
    const canApply = hasPendingGpuApplyAction(input);
    const resetButton = resolveIndexedButton('gpu-reset-round-btn', input.index);
    if (resetButton) {
        resetButton.hidden = !hasManualSnapshotControl(input.snapshot);
        setButtonDisabledState(resetButton, input.pending);
    }
    const historyButton = resolveIndexedButton('gpu-history-round-btn', input.index);
    if (historyButton) {
        setButtonDisabledState(historyButton, input.pending);
    }
    const testButton = resolveIndexedButton('gpu-test-btn', input.index);
    if (testButton) {
        setButtonDisabledState(testButton, input.pending || input.saveMode || canApply);
    }
    const applyButton = resolveIndexedButton('gpu-apply-btn', input.index);
    if (applyButton) {
        setLoadingButtonState(dom, applyButton, input.pending);
        if (!input.pending) {
            setButtonDisabledState(applyButton, !canApply);
        }
    }
    for (const slotButton of resolveIndexedButtons('gpu-slot-button', input.index)) {
        const slotId = slotButton.dataset['slotId'] ?? null;
        slotButton.classList.toggle('is-flashing', input.saveMode);
        slotButton.classList.toggle('gpu-slot-button--active', slotId !== null && input.activeSlot === slotId);
        slotButton.classList.toggle('gpu-slot-button--preview', slotId !== null && input.previewSlot === slotId);
        slotButton.classList.toggle('gpu-slot-button--boot', slotId !== null && input.bootSlot === slotId);
    }
};

export { requiresGpuPrimaryActionRender };
