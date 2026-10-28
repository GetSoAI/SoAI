/* SoAI - Inline GPU control value editing [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlValueEditorController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { dom } from '@core/dom/dom.ts';
import type { GpuCapabilitiesByIndex } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import { focusAndSelectInlineTextEditInput, resolveInlineTextEditKeyAction } from '@core/ui/inlineedit/controller.ts';
import { GPU_CONTROLS_CONFIG } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';
import { getOffsetControlContext } from '@pages/hardware/controllers/gpucontrol/gpuControlNormalization.ts';
import type { GpuControlType, GpuUiState, SliderElements } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';
import { resolveClockDomain } from '@pages/hardware/controllers/gpucontrol/gpuClockDomain.ts';
import { isControlSupported, isGpuControlType } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/guards.ts';

interface GpuValueEditorHost {
    gpuCapabilities: GpuCapabilitiesByIndex | null;
    ensureGpuUiState(index: string | number): GpuUiState;
    isCertifiedRunLocked(index: string | number): boolean;
    getSliderElements(index: string | number, type: string): SliderElements;
    markGpuSettingsEdited(index: string | number): void;
    updateSliderAutoState(index: string | number, type: string, isAuto: boolean): void;
    markGpuStateHydrated(index: string | number): void;
    refreshApplyState(index: string | number): void;
    setSliderToManual(index: string | number, type: string, value: number, options: { alignToSupportedValue: boolean }): void;
}

const readEditorIdentity = (element: HTMLElement): { index: string; type: GpuControlType } => {
    const index = requireTrimmedDataAttribute(element, 'gpuIndex', 'GPU value editor');
    const type = requireTrimmedDataAttribute(element, 'sliderType', 'GPU value editor');
    if (!isGpuControlType(type)) throw new Error('GPU value editor requires a supported control type');
    return { index, type };
};

const isGpuValueEditing = (input: HTMLInputElement): boolean => input.closest('.gpu-slider-value-editor')?.classList.contains('is-editing') === true;

const readGpuEditorValue = (capabilities: GpuCapabilitiesByIndex | null, index: string | number, type: GpuControlType, input: HTMLInputElement): number | null => {
    const value = input.valueAsNumber;
    if (!input.validity.valid || input.value === '' || !Number.isSafeInteger(value) || !isControlSupported(capabilities, index, type, 'manual')) return null;
    const capability = capabilities?.[String(index)]?.[GPU_CONTROLS_CONFIG[type].capabilityKey];
    if (!capability) return null;
    if (type === 'core' || type === 'memory') {
        const domain = resolveClockDomain(capability);
        if (domain.type === 'invalid') return null;
        const absolute = value + (getOffsetControlContext(capabilities, index, type)?.defaultAbs ?? 0);
        if (domain.type === 'discrete' && !domain.values.includes(absolute)) return null;
    }
    return value;
};

const hasInvalidGpuValueEdits = (document: Document, capabilities: GpuCapabilitiesByIndex | null, index?: string | number): boolean => {
    for (const input of dom.resolveAll('.gpu-slider-value-editor.is-editing .gpu-slider-value-input', document)) {
        if (!(input instanceof HTMLInputElement)) throw new Error('GPU value editor must be an input');
        const identity = readEditorIdentity(input);
        if (index !== undefined && identity.index !== String(index)) continue;
        if (readGpuEditorValue(capabilities, identity.index, identity.type, input) === null) return true;
    }
    return false;
};

const startGpuValueEdit = (controller: GpuValueEditorHost, trigger: HTMLElement): void => {
    const { index, type } = readEditorIdentity(trigger);
    if (controller.ensureGpuUiState(index).pending || controller.isCertifiedRunLocked(index)) return;
    const { slider, toggle, toggleLabel, valueInput } = controller.getSliderElements(index, type);
    if (!slider || !toggle || !toggleLabel || !valueInput) throw new Error('GPU value editor controls are missing');
    if (slider.disabled || valueInput.disabled || isGpuValueEditing(valueInput)) return;
    if (toggle.checked) {
        controller.markGpuSettingsEdited(index);
        controller.updateSliderAutoState(index, type, false);
        controller.markGpuStateHydrated(index);
        controller.refreshApplyState(index);
        return;
    }
    valueInput.value = slider.value;
    toggleLabel.classList.add('is-editing');
    focusAndSelectInlineTextEditInput(valueInput);
};

const finishGpuValueEdit = (controller: GpuValueEditorHost, input: HTMLInputElement, action: 'commit' | 'cancel', focus: 'slider' | 'trigger' | 'preserve'): void => {
    if (!isGpuValueEditing(input)) return;
    const { index, type } = readEditorIdentity(input);
    if (controller.ensureGpuUiState(index).pending || controller.isCertifiedRunLocked(index)) return;
    const value = readGpuEditorValue(controller.gpuCapabilities, index, type, input);
    const empty = input.value === '' && !input.validity.badInput;
    if (action === 'commit' && value === null && !empty) {
        controller.refreshApplyState(index);
        return;
    }
    const { toggleLabel } = controller.getSliderElements(index, type);
    if (!toggleLabel) throw new Error('GPU value editor label is missing');
    toggleLabel.classList.remove('is-editing');
    input.removeAttribute('aria-invalid');
    if (action === 'commit' && value !== null) {
        controller.markGpuSettingsEdited(index);
        controller.setSliderToManual(index, type, value, { alignToSupportedValue: false });
        controller.markGpuStateHydrated(index);
    }
    controller.refreshApplyState(index);
    const elements = controller.getSliderElements(index, type);
    if (focus === 'slider') elements.slider?.focus({ preventScroll: true });
    if (focus === 'trigger') elements.valueTrigger?.focus({ preventScroll: true });
};

const discardGpuValueEdit = (controller: GpuValueEditorHost, index: string | number, type: string): void => {
    const { valueInput } = controller.getSliderElements(index, type);
    if (valueInput) finishGpuValueEdit(controller, valueInput, 'cancel', 'preserve');
};

const handleGpuValueInput = (controller: GpuValueEditorHost, element: HTMLElement): void => {
    if (!(element instanceof HTMLInputElement)) throw new Error('GPU value editor must be an input');
    if (isGpuValueEditing(element)) controller.refreshApplyState(readEditorIdentity(element).index);
};

const handleGpuValueKeydown = (controller: GpuValueEditorHost, event: KeyboardEvent, element: HTMLElement): void => {
    if (!(element instanceof HTMLInputElement)) throw new Error('GPU value editor must be an input');
    if (event.isComposing || !isGpuValueEditing(element)) return;
    const action = resolveInlineTextEditKeyAction(event);
    if (action !== null) finishGpuValueEdit(controller, element, action === 'save' ? 'commit' : 'cancel', action === 'save' ? 'slider' : 'trigger');
};

const handleGpuValueFocusOut = (controller: GpuValueEditorHost, event: FocusEvent): void => {
    if (event.target instanceof HTMLInputElement && event.target.classList.contains('gpu-slider-value-input')) finishGpuValueEdit(controller, event.target, 'commit', 'preserve');
};

const preserveGpuValueEditors = (existing: HTMLElement, created: HTMLElement): void => {
    if (existing.dataset['deviceId'] !== created.dataset['deviceId']) return;
    for (const input of dom.resolveAll('.gpu-slider-value-editor.is-editing .gpu-slider-value-input', existing)) {
        if (!(input instanceof HTMLInputElement)) throw new Error('GPU value editor must be an input');
        const { index, type } = readEditorIdentity(input);
        const nextInput = dom.resolve(`#gpu-${index}-${type}-value-input`, created);
        if (!(nextInput instanceof HTMLInputElement) || nextInput.disabled) continue;
        nextInput.closest('.gpu-slider-value-editor')?.classList.add('is-editing');
    }
};

export { discardGpuValueEdit, handleGpuValueFocusOut, handleGpuValueInput, handleGpuValueKeydown, hasInvalidGpuValueEdits, isGpuValueEditing, preserveGpuValueEditors, readGpuEditorValue, startGpuValueEdit };
