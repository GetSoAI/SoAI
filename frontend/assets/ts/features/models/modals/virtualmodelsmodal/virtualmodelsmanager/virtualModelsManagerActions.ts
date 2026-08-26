/* SoAI - Virtual model manager actions [frontend/assets/ts/features/models/modals/virtualmodelsmodal/virtualmodelsmanager/virtualModelsManagerActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { normalizeModelRecord } from '@core/models/modelRecordNormalization.ts';
import { hasFunctionProperty, isArray, isObject, isPlainObject, isString } from '@core/typeGuards.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { isJsonValue } from '@core/types/jsonValues.ts';
import { MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID, MODELS_VIRTUAL_MODELS_MODAL_ID } from '@features/models/modals/constants.ts';
import type { VirtualModelsHost, VirtualModelState } from '@features/models/modals/virtualmodelsmodal/virtualModelsManagerTypes.ts';
import { attachConstituentPicker, renderConstituentPicker } from '@features/models/modals/virtualmodelsmodal/constituentpicker/dom.ts';
import type { ModelsCollectionView, VirtualModelSelectionPayload, VirtualModelsValueControl } from '@features/models/modals/virtualmodelsmodal/virtualmodelsmanager/contracts.ts';

const isModelsCollectionView = <T>(value: T): value is T & ModelsCollectionView => isPlainObject(value) && hasFunctionProperty(value, 'getAll');

const clearVirtualModelsSubscription = (state: VirtualModelState): void => {
    const activeSubscription = state.subscription;
    if (!activeSubscription) {
        return;
    }
    try {
        activeSubscription.unsubscribe();
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('VirtualModelsController', 'Virtual models unsubscribe failed', runtimeError);
    } finally {
        state.subscription = null;
    }
};

const resolveVirtualModelsValueControl = (host: VirtualModelsHost, selector: string, context?: Element): VirtualModelsValueControl => {
    const element = host.view.requireHTMLElement(selector, context);
    if (element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement) {
        return element;
    }
    throw new TypeError(`Virtual models control ${selector} must be an input/select/textarea element`);
};

const requireVirtualModels = (host: VirtualModelsHost): ModelRecord[] => {
    const collectionValue = host.data.getCollection();
    if (!isModelsCollectionView(collectionValue)) {
        throw new Error('VirtualModelsManager requires a collection with getAll()');
    }
    const list = collectionValue.getAll();
    if (!isArray(list)) {
        throw new TypeError('VirtualModelsManager expected collection.getAll() to return an array');
    }
    const models: ModelRecord[] = [];
    for (const item of list) {
        if (!isObject(item) || isArray(item)) {
            throw new TypeError('VirtualModelsManager expected collection models to be objects');
        }
        const id = toTrimmedString(item['id']);
        const name = toTrimmedString(item['name']);
        const universalId = toTrimmedString(item['universalId']);
        if (!universalId && !id && !name) {
            continue;
        }
        if (!isJsonValue(item)) {
            throw new TypeError('VirtualModelsManager expected JSON-compatible collection models');
        }
        const normalized = normalizeModelRecord(item);
        if (!normalized) {
            throw new TypeError('VirtualModelsManager expected valid decoded model records');
        }
        models.push(normalized);
    }
    return models;
};

const collectVirtualModelSelection = (host: VirtualModelsHost, selector: string | Element, context?: Element): VirtualModelSelectionPayload[] => {
    const selectCandidate = isString(selector) ? host.view.requireHTMLElement(selector, context) : selector;
    if (!(selectCandidate instanceof HTMLSelectElement)) {
        throw new TypeError('Virtual model selection requires an HTMLSelectElement');
    }

    return Array.from(selectCandidate.selectedOptions ?? []).map((option: HTMLOptionElement) => {
        const universalId = option.value;
        return { universalId: universalId };
    });
};

const bindVirtualModelSelectionControls = (host: VirtualModelsHost, onFieldChange: () => void): void => {
    const createModalId = MODELS_VIRTUAL_MODELS_MODAL_ID;
    const editModalId = MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID;
    const createModalRoot = host.view.modals.requireElement(createModalId);
    const editModalRoot = host.view.modals.requireElement(editModalId);
    const bindSelection = (id: string): void => {
        const element = host.view.requireHTMLElement(modalUiSelector(createModalId, id), createModalRoot);
        if (element.dataset['vmBound']) {
            return;
        }
        element.dataset['vmBound'] = 'true';
        host.data.on(element, 'change', () => {
            onFieldChange();
        });
    };
    const bindField = (modalId: string, modalRoot: Element, id: string, eventName: 'input' | 'change'): void => {
        const element = host.view.requireHTMLElement(modalUiSelector(modalId, id), modalRoot);
        const isBound = eventName === 'input' ? element.dataset['vmInputBound'] : element.dataset['vmChangeBound'];
        if (isBound) {
            return;
        }
        if (eventName === 'input') {
            element.dataset['vmInputBound'] = 'true';
        } else {
            element.dataset['vmChangeBound'] = 'true';
        }
        host.data.on(element, eventName, onFieldChange);
    };
    const bindStrategyPersistence = (modalId: string, modalRoot: Element, id: string): void => {
        const element = host.view.requireHTMLElement(modalUiSelector(modalId, id), modalRoot);
        if (!(element instanceof HTMLSelectElement)) {
            throw new TypeError(`Virtual models strategy control ${id} must be an HTMLSelectElement`);
        }
        if (element.dataset['vmStrategyPersistBound']) {
            return;
        }
        element.dataset['vmStrategyPersistBound'] = 'true';
        host.data.on(element, 'change', () => {
            const next = element.value;
            if (next === 'load_balancing' || next === 'failover') {
                host.preferences.setLastVirtualModelStrategy(next);
            }
        });
    };
    bindSelection('vm-models');
    bindField(createModalId, createModalRoot, 'vm-name', 'input');
    bindField(createModalId, createModalRoot, 'vm-strategy', 'change');
    bindStrategyPersistence(createModalId, createModalRoot, 'vm-strategy');
    bindField(editModalId, editModalRoot, 'vm-edit-strategy', 'change');
    bindField(editModalId, editModalRoot, 'vm-edit-models', 'change');
    const requireAllModels = (): ModelRecord[] => requireVirtualModels(host);
    attachConstituentPicker({ host, modalId: createModalId, token: 'vm-models', modalRoot: createModalRoot, requireAllModels });
    attachConstituentPicker({ host, modalId: editModalId, token: 'vm-edit-models', modalRoot: editModalRoot, requireAllModels });
};

const renderVirtualModelConstituentPicker = (host: VirtualModelsHost, token: string, selectedIds?: string[]): void => {
    const modalId = token.startsWith('vm-edit-') ? MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID : MODELS_VIRTUAL_MODELS_MODAL_ID;
    const modalRoot = host.view.modals.requireElement(modalId);
    renderConstituentPicker({ host, modalId, token, modalRoot, requireAllModels: () => requireVirtualModels(host) }, selectedIds);
};

export { bindVirtualModelSelectionControls, clearVirtualModelsSubscription, collectVirtualModelSelection, renderVirtualModelConstituentPicker, requireVirtualModels, resolveVirtualModelsValueControl };
