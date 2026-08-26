/* SoAI - Virtual model modal state [frontend/assets/ts/features/models/modals/virtualmodelsmodal/virtualmodels/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { arraysEqual } from '@core/primitives/equality.ts';
import { updateTabAvailabilityState, updateTabSelectionState } from '@core/ui/controls/tabs/effects.ts';
import { MODELS_VIRTUAL_MODELS_MODAL_ID } from '@features/models/modals/constants.ts';
import type { VirtualModelsHost, VirtualModelsPrimaryTab, VirtualModelState } from '@features/models/modals/virtualmodelsmodal/virtualModelsManagerTypes.ts';

const VIRTUAL_MODELS_MODAL_ID = MODELS_VIRTUAL_MODELS_MODAL_ID;

const createInitialVirtualModelState = (): VirtualModelState => {
    return {
        virtualModelCount: 0,
        virtualModelCache: [],
        subscription: null,
        activeTab: 'create',
        editModalOpen: false,
        directEditSession: false,
        originalCreateName: '',
        originalCreateStrategy: '',
        originalCreateModels: [],
        originalEditStrategy: '',
        originalEditModels: []
    };
};

const getSelectedModelIds = (selectElement: HTMLSelectElement): string[] => Array.from(selectElement.selectedOptions ?? []).map((option: HTMLOptionElement) => option.value);

const updateVirtualTabs = (host: VirtualModelsHost, state: VirtualModelState, active: VirtualModelsPrimaryTab, valueControl: (selector: string) => HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement, notifyChanged: () => void): void => {
    state.activeTab = active;
    const modalRoot = host.view.modals.requireElement(VIRTUAL_MODELS_MODAL_ID);
    ['create', 'list'].forEach((id) => {
        const isActive = active === id;
        const tab = host.view.requireHTMLElement(modalUiSelector(VIRTUAL_MODELS_MODAL_ID, `vm-tab-${id}`), modalRoot);
        const sectionId = id === 'create' ? 'vm-form-create' : 'vm-list';
        const section = host.view.requireHTMLElement(modalUiSelector(VIRTUAL_MODELS_MODAL_ID, sectionId), modalRoot);
        host.view.toggleClassName(tab, 'is-active', isActive);
        host.view.toggleClassName(section, 'u-hidden', !isActive);
        updateTabSelectionState(tab, section, isActive);
    });
    const createButton = host.view.requireHTMLElement(modalUiSelector(VIRTUAL_MODELS_MODAL_ID, 'vm-save-create'), modalRoot);
    const shouldHide = active !== 'create';
    host.view.toggleClassName(createButton, 'u-hidden', shouldHide);
    createButton.hidden = shouldHide;
    if (active === 'create') {
        state.originalCreateName = '';
        const strategyControl = valueControl('vm-strategy');
        state.originalCreateStrategy = strategyControl.value;
        state.originalCreateModels = [];
    }
    notifyChanged();
};

const updateVirtualTabControls = (host: VirtualModelsHost, state: VirtualModelState): void => {
    const hasAny = state.virtualModelCount > 0;
    const modalRoot = host.view.modals.requireElement(VIRTUAL_MODELS_MODAL_ID);
    const listTab = host.view.requireHTMLElement(modalUiSelector(VIRTUAL_MODELS_MODAL_ID, 'vm-tab-list'), modalRoot);
    host.view.toggleClassName(listTab, 'u-hidden', !hasAny);
    updateTabAvailabilityState(listTab, hasAny);
    if (!hasAny) {
        state.activeTab = 'create';
        const createTab = host.view.requireHTMLElement(modalUiSelector(VIRTUAL_MODELS_MODAL_ID, 'vm-tab-create'), modalRoot);
        const createPanel = host.view.requireHTMLElement(modalUiSelector(VIRTUAL_MODELS_MODAL_ID, 'vm-form-create'), modalRoot);
        const listPanel = host.view.requireHTMLElement(modalUiSelector(VIRTUAL_MODELS_MODAL_ID, 'vm-list'), modalRoot);
        host.view.addClassName(createTab, 'is-active');
        host.view.toggleClassName(listTab, 'is-active', false);
        host.view.toggleClassName(createPanel, 'u-hidden', false);
        host.view.addClassName(listPanel, 'u-hidden');
        updateTabSelectionState(createTab, createPanel, true);
        updateTabSelectionState(listTab, listPanel, false);
    }
};

const updateCreateAvailability = (host: VirtualModelsHost): void => {
    const modalRoot = host.view.modals.requireElement(VIRTUAL_MODELS_MODAL_ID);
    const element = host.view.requireHTMLElement(modalUiSelector(VIRTUAL_MODELS_MODAL_ID, 'vm-tab-create'), modalRoot);
    if (!(element instanceof HTMLButtonElement)) {
        throw new TypeError('Virtual models create tab control must be an HTMLButtonElement');
    }
    element.disabled = false;
};

const hasCommonChanges = (state: VirtualModelState, valueControl: (selector: string) => HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement, mode: 'create' | 'edit'): boolean => {
    const prefix = mode === 'create' ? 'vm' : 'vm-edit';
    const strategyControl = valueControl(`${prefix}-strategy`);
    const strategy = strategyControl.value;
    const modelsControl = valueControl(`${prefix}-models`);
    if (!(modelsControl instanceof HTMLSelectElement)) {
        throw new TypeError('Virtual model selector must be an HTMLSelectElement');
    }
    const models = getSelectedModelIds(modelsControl);
    if (models.length < 2) return false;
    const originalStrategy = mode === 'create' ? state.originalCreateStrategy : state.originalEditStrategy;
    const originalModels = mode === 'create' ? state.originalCreateModels : state.originalEditModels;
    if (strategy !== originalStrategy) return true;
    return !arraysEqual(models, originalModels);
};

const hasCreateFormChanges = (state: VirtualModelState, valueControl: (selector: string) => HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement): boolean => {
    if (state.activeTab !== 'create') {
        return false;
    }
    const nameControl = valueControl('vm-name');
    if (!(nameControl instanceof HTMLInputElement) && !(nameControl instanceof HTMLTextAreaElement)) {
        throw new TypeError('Virtual model name control must be an input or textarea element');
    }
    const name = readTrimmedInputValue(nameControl);
    const modelsControl = valueControl('vm-models');
    if (!(modelsControl instanceof HTMLSelectElement)) {
        throw new TypeError('Virtual model selector must be an HTMLSelectElement');
    }
    const models = getSelectedModelIds(modelsControl);
    const hasMinimumInput = name !== '' && models.length >= 2;
    if (!hasMinimumInput) return false;
    if (name !== state.originalCreateName) return true;
    return hasCommonChanges(state, valueControl, 'create');
};

const hasEditFormChanges = (state: VirtualModelState, valueControl: (selector: string) => HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement): boolean => {
    const strategyControl = valueControl('vm-edit-strategy');
    const strategy = strategyControl.value;
    const modelsControl = valueControl('vm-edit-models');
    if (!(modelsControl instanceof HTMLSelectElement)) {
        throw new TypeError('Virtual model selector must be an HTMLSelectElement');
    }
    const models = getSelectedModelIds(modelsControl);
    if (strategy !== state.originalEditStrategy) return true;
    return !arraysEqual(models, state.originalEditModels);
};

const getVirtualModelFormValidationErrorKey = (name: string | null | undefined, models: { universalId: string }[]): string | null => {
    const normalizedName = toTrimmedString(name);
    if (!normalizedName || !/^[a-zA-Z0-9/._ -]+$/.test(normalizedName) || !/[a-zA-Z0-9]/.test(normalizedName)) {
        return 'models.modal.virtualModels.invalidName';
    }
    if (!models || models.length === 0) {
        return 'models.modal.virtualModels.noModelsSelected';
    }
    if (models.length < 2) {
        return 'models.modal.virtualModels.minimumTwoModels';
    }
    return null;
};

const isVirtualModelFormValid = (state: VirtualModelState, mode: 'create' | 'edit', name: string | null | undefined, models: { universalId: string }[]): boolean => {
    if (mode === 'create' && state.activeTab !== 'create') {
        return false;
    }
    return getVirtualModelFormValidationErrorKey(name, models) === null;
};

const validateVirtualModelForm = (host: VirtualModelsHost, state: VirtualModelState, mode: 'create' | 'edit', name: string | null | undefined, models: { universalId: string }[]): string | null => {
    if (mode === 'create' && state.activeTab !== 'create') {
        return 'models.modal.virtualModels.invalidName';
    }
    const normalizedName = toTrimmedString(name);
    const errorKey = getVirtualModelFormValidationErrorKey(normalizedName, models);
    if (errorKey) {
        if (errorKey === 'models.modal.virtualModels.invalidName') {
            host.view.showNotification(i18n.t('models.modal.virtualModels.invalidName'), 'error');
        } else if (errorKey === 'models.modal.virtualModels.noModelsSelected') {
            host.view.showNotification(i18n.t('models.modal.virtualModels.noModelsSelected'), 'error');
        } else if (errorKey === 'models.modal.virtualModels.minimumTwoModels') {
            host.view.showNotification(i18n.t('models.modal.virtualModels.minimumTwoModels'), 'error');
        } else {
            throw new Error(`Unhandled virtual model validation key: ${errorKey}`);
        }
        return null;
    }
    return normalizedName;
};

export { createInitialVirtualModelState, hasCommonChanges, hasCreateFormChanges, hasEditFormChanges, isVirtualModelFormValid, validateVirtualModelForm, updateCreateAvailability, updateVirtualTabControls, updateVirtualTabs };
