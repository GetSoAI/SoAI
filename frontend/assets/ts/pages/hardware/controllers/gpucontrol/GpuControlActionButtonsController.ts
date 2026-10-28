/* SoAI - Hardware page GPU control action buttons controller [frontend/assets/ts/pages/hardware/controllers/gpucontrol/GpuControlActionButtonsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isPresenceExiting } from '@core/animations/presence/public.ts';
import { getBusyDisabledToken } from '@core/ui/controls/busyDisabledState.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { setLoadingButtonState } from '@core/ui/loadingbuttons/service.ts';
import { type GpuPrimaryAction, hasPendingGpuApplyAction } from '@pages/hardware/controllers/gpucontrol/gpuControlPrimaryActionController.ts';
import { normalizeSnapshot } from '@pages/hardware/controllers/gpucontrol/gpuControlNormalization.ts';
import { hasGpuResettableSettings } from '@pages/hardware/controllers/gpucontrol/gpuControlValidation.ts';
import { hasInvalidGpuValueEdits } from '@pages/hardware/controllers/gpucontrol/gpuControlValueEditorController.ts';
import { syncGpuControlInputAvailability } from '@pages/hardware/controllers/gpucontrol/gpuControlAvailabilityController.ts';
import type { GpuCapabilitiesByIndex, GpuCapabilities } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { GpuSettingsState, GpuSnapshot } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

interface SyncGpuControlActionButtonsInput {
    index: string;
    snapshot: GpuSnapshot;
    capabilities: GpuCapabilities | null;
    capabilitiesByIndex: GpuCapabilitiesByIndex | null;
    liveSettings: GpuSettingsState | null;
    pending: boolean;
    locked: boolean;
    saveMode: boolean;
    canStoreAppliedSettings: boolean;
    canSaveCurrentSettings: boolean;
    applyCapability: { canApply: boolean } | null;
    activeSlot: string | null;
    previewSlot: string | null;
    bootSlot: string | null;
}

const resolveIndexedButton = (className: string, index: string): HTMLButtonElement | null => {
    for (const element of dom.resolveAll(`.${className}`)) {
        if (element instanceof HTMLButtonElement && element.dataset['gpuIndex'] === index && !isPresenceExiting(element)) {
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

const requiresGpuPrimaryActionRender = (index: string, primaryAction: GpuPrimaryAction, locked: boolean): boolean => {
    if (locked || !hasMountedGpuControlPanel(index)) {
        return false;
    }
    const saveButton = resolveIndexedButton('gpu-save-btn', index);
    const applyButton = resolveIndexedButton('gpu-apply-btn', index);
    return primaryAction === 'save' ? !saveButton : !applyButton;
};

export const GpuControlActionButtonsController = (input: SyncGpuControlActionButtonsInput): void => {
    syncGpuControlInputAvailability(document, input.capabilitiesByIndex, input.index, input.pending, input.locked, input.previewSlot);
    const canApply = hasPendingGpuApplyAction(input);
    const invalidValue = hasInvalidGpuValueEdits(document, input.capabilitiesByIndex, input.index);
    const resetButton = resolveIndexedButton('gpu-reset-round-btn', input.index);
    if (resetButton) {
        resetButton.hidden = !hasGpuResettableSettings(input.capabilities, input.liveSettings, normalizeSnapshot(input.snapshot));
        setControlDisabledState(resetButton, input.pending || input.locked);
    }
    const historyButton = resolveIndexedButton('gpu-history-round-btn', input.index);
    if (historyButton) {
        setControlDisabledState(historyButton, input.pending);
    }
    const testButton = resolveIndexedButton('gpu-test-btn', input.index);
    if (testButton) {
        setControlDisabledState(testButton, input.pending || input.saveMode || canApply || invalidValue);
    }
    const saveButton = resolveIndexedButton('gpu-save-btn', input.index);
    if (saveButton) {
        setControlDisabledState(saveButton, input.pending || input.locked || invalidValue || getBusyDisabledToken(saveButton) !== null);
    }
    const applyButton = resolveIndexedButton('gpu-apply-btn', input.index);
    if (applyButton) {
        setLoadingButtonState(dom, applyButton, input.pending);
        if (!input.pending) {
            setControlDisabledState(applyButton, !canApply || invalidValue);
        }
    }
    for (const slotButton of resolveIndexedButtons('gpu-slot-button', input.index)) {
        const slotId = slotButton.dataset['slotId'] ?? null;
        setControlDisabledState(slotButton, input.pending || input.locked || invalidValue || (!input.saveMode && slotButton.classList.contains('gpu-slot-button--empty')));
        slotButton.classList.toggle('is-flashing', input.saveMode);
        slotButton.classList.toggle('gpu-slot-button--active', slotId !== null && input.activeSlot === slotId);
        slotButton.classList.toggle('gpu-slot-button--preview', slotId !== null && input.previewSlot === slotId);
        slotButton.classList.toggle('gpu-slot-button--boot', slotId !== null && input.bootSlot === slotId);
    }
};

export { requiresGpuPrimaryActionRender };
