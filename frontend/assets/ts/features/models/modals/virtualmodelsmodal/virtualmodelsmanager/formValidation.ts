/* SoAI - Models feature form validation [frontend/assets/ts/features/models/modals/virtualmodelsmodal/virtualmodelsmanager/formValidation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiSelector } from '@core/modals/uiIds.ts';
import { MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID } from '@features/models/modals/constants.ts';
import { isVirtualModelFormValid } from '@features/models/modals/virtualmodelsmodal/virtualmodels/state.ts';
import type { VirtualModelState, VirtualModelsHost } from '@features/models/modals/virtualmodelsmodal/virtualModelsManagerTypes.ts';
import { resolveVirtualModelsValueControl } from '@features/models/modals/virtualmodelsmodal/virtualmodelsmanager/virtualModelsManagerActions.ts';

type VirtualModelSelectionReader = (selector: string | Element, context?: Element) => { universalId: string }[];
type VirtualModelsValueControlResolver = (token: string) => HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

const createVirtualModelsValueControlResolver = (host: VirtualModelsHost, modalId: string): VirtualModelsValueControlResolver => {
    return (token: string): HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement => {
        const resolvedModalId = token.startsWith('vm-edit-') ? MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID : modalId;
        const modalRoot = host.view.modals.requireElement(resolvedModalId);
        return resolveVirtualModelsValueControl(host, modalUiSelector(resolvedModalId, token), modalRoot);
    };
};

const isCreateVirtualModelFormValid = (host: VirtualModelsHost, state: VirtualModelState, modalId: string, collectSelectedModels: VirtualModelSelectionReader, valueControl: VirtualModelsValueControlResolver): boolean => {
    const modalRoot = host.view.modals.requireElement(modalId);
    const models = collectSelectedModels(modalUiSelector(modalId, 'vm-models'), modalRoot);
    const nameControl = valueControl('vm-name');
    if (!(nameControl instanceof HTMLInputElement)) {
        throw new TypeError('Virtual model name control must be an input element');
    }
    const name = nameControl.value;
    return isVirtualModelFormValid(state, 'create', name, models);
};

const isEditVirtualModelFormValid = (host: VirtualModelsHost, state: VirtualModelState, collectSelectedModels: VirtualModelSelectionReader): boolean => {
    if (!state.editModalOpen) {
        return true;
    }
    const editModalRoot = host.view.modals.requireElement(MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID);
    const models = collectSelectedModels(modalUiSelector(MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID, 'vm-edit-models'), editModalRoot);
    const saveButton = host.view.requireHTMLElement(modalUiSelector(MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID, 'vm-save-edit'), editModalRoot);
    const vmName = host.view.dom.getData(saveButton, 'vmName');
    return isVirtualModelFormValid(state, 'edit', vmName, models);
};

export { createVirtualModelsValueControlResolver, isCreateVirtualModelFormValid, isEditVirtualModelFormValid };
export type { VirtualModelsValueControlResolver };
