/* SoAI - Models feature operations [frontend/assets/ts/features/models/modals/virtualmodelsmodal/virtualmodels/operations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID, MODELS_VIRTUAL_MODELS_MODAL_ID } from '@features/models/modals/constants.ts';
import type { ModelEntry, VirtualModelsHost, VirtualModelsPrimaryTab, VirtualModelRecord, VirtualModelState } from '@features/models/modals/virtualmodelsmodal/virtualModelsManagerTypes.ts';
import { decodeVirtualModelCreateRequest, decodeVirtualModelUpdateRequest } from '@core/api/contracts/virtualModelContracts.ts';

const VIRTUAL_MODELS_MODAL_ID = MODELS_VIRTUAL_MODELS_MODAL_ID;
const VM_EDIT_MODAL_ID = MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID;

interface ProcessVirtualModelActionDependencies {
    host: VirtualModelsHost;
    state: VirtualModelState;
    loadVirtualModelsList(): void;
    closeVmEditModal(): void;
    resetCreateForm(): void;
    updateVirtualTabs(active: VirtualModelsPrimaryTab): void;
}

interface ShowEditVirtualModelFormDependencies {
    host: VirtualModelsHost;
    state: VirtualModelState;
    isActive(): boolean;
    renderConstituentPicker(token: string, selectedIds: string[]): void;
    notifyChanged(): void;
}

interface CreateVirtualModelDependencies {
    valueControl(selector: string): HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
    collectSelectedModels(selector: string | Element): { universalId: string }[];
    validateVirtualModelForm(name: string | null | undefined, models: { universalId: string }[]): string | null;
    processVirtualModelAction(actionType: 'create' | 'update', name: string | null, payload: JsonObject): Promise<void>;
}

interface SaveEditedVirtualModelDependencies extends CreateVirtualModelDependencies {
    host: VirtualModelsHost;
}

interface DeleteVirtualModelDependencies {
    host: VirtualModelsHost;
    loadVirtualModelsList(): void;
}

interface DisposeVirtualModelsManagerDependencies {
    host: VirtualModelsHost;
    state: VirtualModelState;
    clearVirtualModelsSubscription(): void;
}

const processVirtualModelAction = async (dependencies: ProcessVirtualModelActionDependencies, actionType: 'create' | 'update', name: string | null, payload: JsonObject): Promise<void> => {
    try {
        if (actionType === 'create') {
            await dependencies.host.data.api.routing.virtualModels.create(decodeVirtualModelCreateRequest(payload));
        } else {
            if (!name) {
                throw new Error('Virtual model update requires a virtual model name');
            }
            await dependencies.host.data.api.routing.virtualModels.update(name, decodeVirtualModelUpdateRequest(payload));
        }
        dependencies.loadVirtualModelsList();
        dependencies.host.view.showNotification(i18n.t('common.success'), 'success');
        if (actionType === 'update') {
            dependencies.closeVmEditModal();
        } else {
            dependencies.resetCreateForm();
            if (dependencies.state.virtualModelCount > 0) {
                dependencies.updateVirtualTabs('list');
            }
        }
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('VirtualModelsController', `Failed to ${actionType} virtual model`, runtimeError);
        if (actionType === 'create') {
            dependencies.host.view.showNotification(i18n.t('models.notifications.virtualModelCreateFailed'), 'error');
        } else {
            dependencies.host.view.showNotification(i18n.t('models.notifications.virtualModelUpdateFailed'), 'error');
        }
    }
};

const showEditVirtualModelForm = async (dependencies: ShowEditVirtualModelFormDependencies, vmName: string | null): Promise<void> => {
    if (!dependencies.isActive()) {
        return;
    }
    if (!vmName) {
        dependencies.host.view.showNotification(i18n.t('models.modal.virtualModels.selectVirtualModel'), 'error');
        return;
    }
    const editModalRoot = dependencies.host.view.modals.requireElement(VM_EDIT_MODAL_ID);
    const summary = dependencies.host.view.requireHTMLElement(modalUiSelector(VM_EDIT_MODAL_ID, 'vm-edit-summary'), editModalRoot);
    dependencies.host.view.updateText(summary, vmName);
    const saveButton = dependencies.host.view.requireHTMLElement(modalUiSelector(VM_EDIT_MODAL_ID, 'vm-save-edit'), editModalRoot);
    try {
        const vmResponse = await dependencies.host.data.api.routing.virtualModels.get(vmName);
        if (!dependencies.isActive()) {
            return;
        }
        const vm: VirtualModelRecord = vmResponse;
        const strategy = vm.strategy;
        const strategyControl = dependencies.host.view.requireHTMLElement(modalUiSelector(VM_EDIT_MODAL_ID, 'vm-edit-strategy'), editModalRoot);
        if (!(strategyControl instanceof HTMLSelectElement)) {
            throw new TypeError('Virtual model edit strategy control must be a select element');
        }
        dependencies.host.view.setUIValue(strategyControl, strategy, { attribute: 'value' });
        const models: ModelEntry[] = vm.models;
        const modelIds = models.map((entry) => entry.universalId);
        dependencies.renderConstituentPicker('vm-edit-models', modelIds);
        dependencies.host.view.dom.setData(saveButton, 'vmName', vmName);
        dependencies.state.originalEditStrategy = strategy;
        dependencies.state.originalEditModels = modelIds;
        dependencies.host.view.modals.open(VM_EDIT_MODAL_ID);
        dependencies.state.editModalOpen = true;
        dependencies.notifyChanged();
    } catch (error) {
        if (!dependencies.isActive()) {
            return;
        }
        const runtimeError = ensureError(error);
        errorHandler.error('VirtualModelsController', 'Failed to load virtual model for editing', runtimeError);
        dependencies.host.view.showNotification(i18n.t('models.notifications.virtualModelLoadFailed'), 'error');
        saveButton.removeAttribute('data-vm-name');
    }
};

const createVirtualModel = async (dependencies: CreateVirtualModelDependencies): Promise<void> => {
    const nameControl = dependencies.valueControl('vm-name');
    const strategyControl = dependencies.valueControl('vm-strategy');
    const name = nameControl.value;
    const strategy = strategyControl.value;
    const models = dependencies.collectSelectedModels(modalUiSelector(VIRTUAL_MODELS_MODAL_ID, 'vm-models'));
    const normalizedName = dependencies.validateVirtualModelForm(name, models);
    if (!normalizedName) return;
    await dependencies.processVirtualModelAction('create', null, { name: normalizedName, strategy, models });
};

const saveEditedVirtualModel = async (dependencies: SaveEditedVirtualModelDependencies): Promise<void> => {
    const editModalRoot = dependencies.host.view.modals.requireElement(VM_EDIT_MODAL_ID);
    const saveButton = dependencies.host.view.requireHTMLElement(modalUiSelector(VM_EDIT_MODAL_ID, 'vm-save-edit'), editModalRoot);
    const vmName = dependencies.host.view.dom.getData(saveButton, 'vmName');
    const strategyControl = dependencies.valueControl('vm-edit-strategy');
    const strategy = strategyControl.value;
    const models = dependencies.collectSelectedModels(modalUiSelector(VM_EDIT_MODAL_ID, 'vm-edit-models'));
    if (!vmName) {
        dependencies.host.view.showNotification(i18n.t('models.modal.virtualModels.selectVirtualModel'), 'error');
        return;
    }
    const normalizedName = dependencies.validateVirtualModelForm(vmName, models);
    if (!normalizedName) return;
    await dependencies.processVirtualModelAction('update', normalizedName, { strategy, models });
};

const deleteVirtualModel = async (dependencies: DeleteVirtualModelDependencies, name: string): Promise<void> => {
    if (!name) {
        throw new Error('Virtual model delete requires a virtual model name');
    }
    const confirmed = await requireDialogsService().showConfirmation({
        title: i18n.t('models.modal.virtualModels.confirmDelete'),
        message: i18n.t('models.modal.virtualModels.confirmDeleteMessage', { name }),
        confirmText: i18n.t('common.delete'),
        cancelText: i18n.t('common.cancel')
    });
    if (!confirmed) return;
    try {
        await dependencies.host.data.api.routing.virtualModels.delete(name);
        dependencies.host.data.removeItemById(name);
        dependencies.loadVirtualModelsList();
        dependencies.host.view.showNotification(i18n.t('models.notifications.deleteSuccess', { model: name }), 'success');
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('VirtualModelsController', 'Failed to delete virtual model', runtimeError);
        dependencies.host.view.showNotification(i18n.t('models.notifications.deleteFailed'), 'error');
    }
};

const disposeVirtualModelsManager = (dependencies: DisposeVirtualModelsManagerDependencies): void => {
    const mainModalRoot = dependencies.host.view.modals.requireElement(VIRTUAL_MODELS_MODAL_ID);
    const nameInput = dependencies.host.view.requireHTMLElement(modalUiSelector(VIRTUAL_MODELS_MODAL_ID, 'vm-name'), mainModalRoot);
    dependencies.host.view.setUIValue(nameInput, '', { attribute: 'value' });
    dependencies.state.originalCreateName = '';
    dependencies.state.originalCreateStrategy = '';
    dependencies.state.originalCreateModels = [];
    dependencies.state.originalEditStrategy = '';
    dependencies.state.originalEditModels = [];
    dependencies.clearVirtualModelsSubscription();
    dependencies.state.activeTab = 'create';
    dependencies.state.editModalOpen = false;
};

export { createVirtualModel, deleteVirtualModel, disposeVirtualModelsManager, processVirtualModelAction, saveEditedVirtualModel, showEditVirtualModelForm };
export type { CreateVirtualModelDependencies, DeleteVirtualModelDependencies, DisposeVirtualModelsManagerDependencies, ProcessVirtualModelActionDependencies, SaveEditedVirtualModelDependencies, ShowEditVirtualModelFormDependencies };
