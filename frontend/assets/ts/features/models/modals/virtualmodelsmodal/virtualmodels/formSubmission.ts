/* SoAI - Models feature form submission [frontend/assets/ts/features/models/modals/virtualmodelsmodal/virtualmodels/formSubmission.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID } from '@features/models/modals/constants.ts';
import type { VirtualModelsHost, VirtualModelState } from '@features/models/modals/virtualmodelsmodal/virtualModelsManagerTypes.ts';
import { createVirtualModel, saveEditedVirtualModel } from '@features/models/modals/virtualmodelsmodal/virtualmodels/operations.ts';
import { validateVirtualModelForm } from '@features/models/modals/virtualmodelsmodal/virtualmodels/state.ts';
import { resolveVirtualModelsValueControl } from '@features/models/modals/virtualmodelsmodal/virtualmodelsmanager/virtualModelsManagerActions.ts';

interface VirtualModelFormSubmissionDependencies {
    host: VirtualModelsHost;
    state: VirtualModelState;
    modalId: string;
    collectSelectedModels(selector: string | Element, context?: Element): { universalId: string }[];
    processModelAction(actionType: 'create' | 'update', name: string | null, payload: JsonObject): Promise<void>;
}

const resolveSubmissionControl = (dependencies: VirtualModelFormSubmissionDependencies, token: string): HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement => {
    const modalId = token.startsWith('vm-edit-') ? MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID : dependencies.modalId;
    const modalRoot = dependencies.host.view.modals.requireElement(modalId);
    return resolveVirtualModelsValueControl(dependencies.host, modalUiSelector(modalId, token), modalRoot);
};

const submitCreateVirtualModel = async (dependencies: VirtualModelFormSubmissionDependencies): Promise<void> => {
    await createVirtualModel({
        valueControl: (token: string): HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement => resolveSubmissionControl(dependencies, token),
        collectSelectedModels: (selector: string | Element): { universalId: string }[] => {
            const modalRoot = dependencies.host.view.modals.requireElement(dependencies.modalId);
            return dependencies.collectSelectedModels(selector, modalRoot);
        },
        validateVirtualModelForm: (name: string | null | undefined, models: { universalId: string }[]): string | null => validateVirtualModelForm(dependencies.host, dependencies.state, 'create', name, models),
        processVirtualModelAction: (actionType: 'create' | 'update', name: string | null, payload: JsonObject): Promise<void> => dependencies.processModelAction(actionType, name, payload)
    });
};

const submitEditedVirtualModel = async (dependencies: VirtualModelFormSubmissionDependencies): Promise<void> => {
    await saveEditedVirtualModel({
        host: dependencies.host,
        valueControl: (token: string): HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement => resolveSubmissionControl(dependencies, token),
        collectSelectedModels: (selector: string | Element): { universalId: string }[] => {
            const editModalRoot = dependencies.host.view.modals.requireElement(MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID);
            return dependencies.collectSelectedModels(selector, editModalRoot);
        },
        validateVirtualModelForm: (name: string | null | undefined, models: { universalId: string }[]): string | null => validateVirtualModelForm(dependencies.host, dependencies.state, 'edit', name, models),
        processVirtualModelAction: (actionType: 'create' | 'update', name: string | null, payload: JsonObject): Promise<void> => dependencies.processModelAction(actionType, name, payload)
    });
};

export { submitCreateVirtualModel, submitEditedVirtualModel };
export type { VirtualModelFormSubmissionDependencies };
