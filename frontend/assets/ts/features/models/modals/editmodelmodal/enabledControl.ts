/* SoAI - Models feature enabled control [frontend/assets/ts/features/models/modals/editmodelmodal/enabledControl.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import { isBoolean } from '@core/typeGuards.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { MODELS_EDIT_MODEL_MODAL_ID } from '@features/models/modals/constants.ts';

interface EditModelEnabledControlHost {
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    updateText(element: Element, text: string): void;
    toggleClassName(target: Element, className: string, enabled?: boolean, context?: Element): void;
    resolveModelStatusBadgeClass(model: ModelRecord): string;
    resolveModelStatusLabel(model: ModelRecord): string;
}

interface EditModelEnabledState {
    modelId: string;
    originalEnabled: boolean;
    currentEnabled: boolean;
}

interface EditModelEnabledApi {
    updateEnabled: (modelId: string, payload: { enabled: boolean }) => Promise<SuccessfulMutationResponse>;
}

const resolveModelEnabled = (model: ModelRecord): boolean => {
    const enabledValue = model.isEnabled;
    return isBoolean(enabledValue) ? enabledValue : true;
};

const createEditModelEnabledState = (model: ModelRecord, modelId: string): EditModelEnabledState => {
    const enabled = resolveModelEnabled(model);
    return {
        modelId,
        originalEnabled: enabled,
        currentEnabled: enabled
    };
};

const hasEditModelEnabledChanges = (state: EditModelEnabledState | null): boolean => Boolean(state && state.originalEnabled !== state.currentEnabled);

const setEditModelEnabled = (state: EditModelEnabledState, enabled: boolean): void => {
    state.currentEnabled = enabled;
};

const parseEditModelEnabledToggleRequest = (element: HTMLElement): boolean => {
    if (element.dataset['busy'] === 'true') {
        throw new Error('Edit model enabled toggle is busy');
    }
    const checkbox = dom.resolve('input[type="checkbox"]', element);
    if (!(checkbox instanceof HTMLInputElement) || checkbox.type !== 'checkbox') {
        throw new TypeError('Edit model enabled toggle requires a checkbox input');
    }
    return checkbox.checked;
};

const populateEditModelEnabledControl = (host: EditModelEnabledControlHost, model: ModelRecord, state: EditModelEnabledState, modalRoot: HTMLElement): void => {
    const field = host.requireHTMLElement(modalUiSelector(MODELS_EDIT_MODEL_MODAL_ID, 'enabled-field'), modalRoot);
    if (model.type === 'virtual') {
        host.toggleClassName(field, 'u-hidden', true, modalRoot);
        return;
    }
    const toggle = host.requireHTMLElement(modalUiSelector(MODELS_EDIT_MODEL_MODAL_ID, 'enabled-toggle'), field);
    const stateLabel = host.requireHTMLElement(modalUiSelector(MODELS_EDIT_MODEL_MODAL_ID, 'enabled-state'), field);
    const checkbox = dom.resolve(modalUiSelector(MODELS_EDIT_MODEL_MODAL_ID, 'enabled-checkbox'), field);
    const toggleLabel = dom.resolve('.toggle-label', toggle);
    const statusBadgeClass = host.resolveModelStatusBadgeClass(model);
    if (!(checkbox instanceof HTMLInputElement) || checkbox.type !== 'checkbox') {
        throw new TypeError('Edit model enabled control requires a checkbox input');
    }
    if (!(toggleLabel instanceof HTMLElement)) {
        throw new TypeError('Edit model enabled control requires a toggle label');
    }
    const enabledLabel = state.currentEnabled ? i18n.t('common.enabled') : i18n.t('common.disabled');
    checkbox.checked = state.currentEnabled;
    checkbox.setAttribute('aria-label', enabledLabel);
    toggle.classList.toggle('toggle-switch--checked', state.currentEnabled);
    host.updateText(toggleLabel, enabledLabel);
    stateLabel.className = ['model-edit-enabled-state', 'ui-metric-badge', 'status-full', statusBadgeClass].filter(Boolean).join(' ');
    host.updateText(stateLabel, host.resolveModelStatusLabel(model));
    host.toggleClassName(stateLabel, 'model-edit-enabled-state--disabled', !state.currentEnabled, modalRoot);
    host.toggleClassName(field, 'u-hidden', false, modalRoot);
};

const setEditModelEnabledControlBusy = (modalRoot: HTMLElement, busy: boolean): void => {
    const toggle = dom.resolve(modalUiSelector(MODELS_EDIT_MODEL_MODAL_ID, 'enabled-toggle'), modalRoot);
    if (!(toggle instanceof HTMLElement)) {
        return;
    }
    const checkbox = dom.resolve('input[type="checkbox"]', toggle);
    if (!(checkbox instanceof HTMLInputElement)) {
        return;
    }
    if (busy) {
        toggle.dataset['busy'] = 'true';
        checkbox.disabled = true;
        return;
    }
    delete toggle.dataset['busy'];
    checkbox.disabled = false;
};

const saveEditModelEnabledState = async (dependencies: { api: EditModelEnabledApi; model: ModelRecord; state: EditModelEnabledState }): Promise<ModelRecord> => {
    const { api, model, state } = dependencies;
    if (!hasEditModelEnabledChanges(state)) {
        return model;
    }
    await api.updateEnabled(state.modelId, { enabled: state.currentEnabled });
    const updatedModel: ModelRecord = {
        ...model,
        isEnabled: state.currentEnabled,
        ...(!state.currentEnabled ? { isAvailable: false } : {})
    };
    state.originalEnabled = state.currentEnabled;
    return updatedModel;
};

export { createEditModelEnabledState, hasEditModelEnabledChanges, parseEditModelEnabledToggleRequest, populateEditModelEnabledControl, saveEditModelEnabledState, setEditModelEnabled, setEditModelEnabledControlBusy };
export type { EditModelEnabledApi, EditModelEnabledState };
