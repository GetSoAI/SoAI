/* SoAI - Virtual model manager [frontend/assets/ts/features/models/modals/virtualmodelsmodal/VirtualModelsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { LifecycleScope, type LifecycleRun } from '@core/lifecycle/lifecycleScope.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { SaveController } from '@core/save/public.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID, MODELS_VIRTUAL_MODELS_MODAL_ID } from '@features/models/modals/constants.ts';
import type { VirtualModelsHost, VirtualModelsManagerDependencies, VirtualModelsPrimaryTab, VirtualModelState } from '@features/models/modals/virtualmodelsmodal/virtualModelsManagerTypes.ts';
import { bindVirtualModelsModalActions } from '@features/models/modals/virtualmodelsmodal/virtualmodels/actionBindings.ts';
import { createVirtualModelFieldStateTracker, syncVirtualModelFieldState } from '@features/models/modals/virtualmodelsmodal/virtualmodels/fieldState.ts';
import { submitCreateVirtualModel, submitEditedVirtualModel } from '@features/models/modals/virtualmodelsmodal/virtualmodels/formSubmission.ts';
import { deleteVirtualModel, disposeVirtualModelsManager, processVirtualModelAction, showEditVirtualModelForm } from '@features/models/modals/virtualmodelsmodal/virtualmodels/operations.ts';
import { openVirtualModelsModal } from '@features/models/modals/virtualmodelsmodal/virtualmodels/service.ts';
import { createInitialVirtualModelState, hasCreateFormChanges, hasEditFormChanges, updateCreateAvailability, updateVirtualTabControls, updateVirtualTabs } from '@features/models/modals/virtualmodelsmodal/virtualmodels/state.ts';
import { loadVirtualModelsList } from '@features/models/modals/virtualmodelsmodal/virtualmodels/view.ts';
import { createVirtualModelsValueControlResolver, isCreateVirtualModelFormValid, isEditVirtualModelFormValid, type VirtualModelsValueControlResolver } from '@features/models/modals/virtualmodelsmodal/virtualmodelsmanager/formValidation.ts';
import { bindVirtualModelSelectionControls, clearVirtualModelsSubscription, collectVirtualModelSelection, renderVirtualModelConstituentPicker, resolveVirtualModelsValueControl } from '@features/models/modals/virtualmodelsmodal/virtualmodelsmanager/virtualModelsManagerActions.ts';
import { createVirtualModelsSaveController } from '@features/models/modals/virtualmodelsmodal/virtualmodelsmanager/saveController.ts';

class VirtualModelsManager {
    readonly modalId = MODELS_VIRTUAL_MODELS_MODAL_ID;
    readonly #host: VirtualModelsHost;
    #listenersScope: LifecycleScope = new LifecycleScope();
    #save: SaveController | null = null;
    #fieldState: FieldStateTracker | null = null;
    state: VirtualModelState;

    constructor({ host }: VirtualModelsManagerDependencies) {
        if (!host) {
            throw new Error('VirtualModelsManager requires a host instance');
        }
        this.#host = host;
        this.state = createInitialVirtualModelState();
    }

    #clearModalState(): void {
        this.#listenersScope.abort('virtual-models-modal-reset');
        this.#fieldState?.clearAll();
        this.#fieldState = null;
        this.#save?.dispose();
        this.#save = null;
        disposeVirtualModelsManager({
            host: this.#host,
            state: this.state,
            clearVirtualModelsSubscription: () => clearVirtualModelsSubscription(this.state)
        });
    }

    #requireActiveLifecycle(actionName: string): LifecycleRun {
        const lifecycle = this.#listenersScope.current();
        if (!this.#listenersScope.isCurrent(lifecycle)) {
            throw new Error(`${actionName} requires an open virtual models modal`);
        }
        return lifecycle;
    }

    #beginSession(): { signal: AbortSignal; modalRoot: HTMLElement; valueControl: VirtualModelsValueControlResolver } {
        const { signal } = this.#listenersScope.begin('virtual-models-modal-open');
        this.#save?.dispose();
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const valueControl = createVirtualModelsValueControlResolver(this.#host, this.modalId);
        this.#fieldState = createVirtualModelFieldStateTracker(this.#host, this.state, valueControl, (selector: string | Element, context?: Element) => this.collectSelectedModels(selector, context));
        this.#save = createVirtualModelsSaveController({
            host: this.#host,
            modalId: this.modalId,
            editModalId: MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID,
            hasCreateChanges: () => hasCreateFormChanges(this.state, valueControl),
            hasEditChanges: () => this.state.editModalOpen && hasEditFormChanges(this.state, valueControl),
            isCreateValid: () => isCreateVirtualModelFormValid(this.#host, this.state, this.modalId, (selector: string | Element, context?: Element) => this.collectSelectedModels(selector, context), valueControl),
            isEditValid: () => isEditVirtualModelFormValid(this.#host, this.state, (selector: string | Element, context?: Element) => this.collectSelectedModels(selector, context)),
            saveCreate: () => this._createVirtualModelAction(),
            saveEdit: () => this._saveEditedVirtualModelAction()
        });
        return { signal, modalRoot, valueControl };
    }

    openVirtualModelsModal(_event?: Event): void {
        const { signal, modalRoot, valueControl } = this.#beginSession();
        this.state.directEditSession = false;
        openVirtualModelsModal({
            host: this.#host,
            state: this.state,
            modalId: this.modalId,
            valueControl,
            renderConstituentPicker: (token: string, selectedIds?: string[]): void => renderVirtualModelConstituentPicker(this.#host, token, selectedIds),
            bindVirtualModelSelectors: (): void => this.bindVirtualModelSelectors(),
            updateVirtualTabControls: (): void => this.updateVirtualTabControls(),
            updateVirtualTabs: (active: VirtualModelsPrimaryTab): void => this.updateVirtualTabs(active),
            loadVirtualModelsList: (): void => this.loadVirtualModelsList(),
            updateCreateAvailability: (): void => this.updateCreateAvailability(),
            notifyChanged: (): void => {
                this.#notifyChanged();
            }
        });
        bindVirtualModelsModalActions({
            root: modalRoot,
            signal,
            showCreateVirtualModelForm: (): void => this.showCreateVirtualModelForm(),
            showVirtualModelsListSection: (): void => this.showVirtualModelsListSection(),
            showEditVirtualModelForm: (name: string): Promise<void> => this.showEditVirtualModelForm(name),
            deleteVirtualModel: (name: string): Promise<void> => this.deleteVirtualModel(name)
        });
    }

    async openVirtualModelEditForm(vmName: string): Promise<void> {
        const normalizedName = vmName.trim();
        if (!normalizedName) {
            return;
        }
        this.#beginSession();
        this.state.directEditSession = true;
        this.bindVirtualModelSelectors();
        await this.showEditVirtualModelForm(normalizedName);
    }

    onModalClosed(): void {
        this.#clearModalState();
    }

    disposeForPageDestroy(): void {
        this.#clearModalState();
    }

    loadVirtualModelsList(): void {
        loadVirtualModelsList({
            host: this.#host,
            state: this.state,
            clearVirtualModelsSubscription: () => clearVirtualModelsSubscription(this.state),
            updateVirtualTabControls: () => this.updateVirtualTabControls(),
            updateVirtualTabs: (active: VirtualModelsPrimaryTab) => this.updateVirtualTabs(active)
        });
    }

    updateVirtualTabControls(): void {
        updateVirtualTabControls(this.#host, this.state);
    }

    updateCreateAvailability(): void {
        updateCreateAvailability(this.#host);
    }

    updateVirtualTabs(active: VirtualModelsPrimaryTab): void {
        updateVirtualTabs(
            this.#host,
            this.state,
            active,
            (token: string): HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement => {
                const modalRoot = this.#host.view.modals.requireElement(this.modalId);
                return resolveVirtualModelsValueControl(this.#host, modalUiSelector(this.modalId, token), modalRoot);
            },
            (): void => {
                this.#notifyChanged();
            }
        );
    }

    showCreateVirtualModelForm(): void {
        this.updateVirtualTabs('create');
    }

    async showEditVirtualModelForm(vmName: string | null = null): Promise<void> {
        const lifecycle = this.#requireActiveLifecycle('VirtualModelsManager edit form');
        await showEditVirtualModelForm(
            {
                host: this.#host,
                state: this.state,
                isActive: (): boolean => this.#listenersScope.isCurrent(lifecycle),
                renderConstituentPicker: (token: string, selectedIds: string[]): void => renderVirtualModelConstituentPicker(this.#host, token, selectedIds),
                notifyChanged: (): void => {
                    this.#notifyChanged();
                }
            },
            vmName
        );
    }

    onVmEditModalClosed(): void {
        this.state.editModalOpen = false;
        if (this.state.directEditSession) {
            this.state.directEditSession = false;
            this.#clearModalState();
            return;
        }
        this.#notifyChanged();
    }

    showVirtualModelsListSection(): void {
        this.updateVirtualTabs('list');
        this.loadVirtualModelsList();
    }

    #resetCreateForm(): void {
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const nameControl = resolveVirtualModelsValueControl(this.#host, modalUiSelector(this.modalId, 'vm-name'), modalRoot);
        this.#host.view.setUIValue(nameControl, '', { attribute: 'value' });
        renderVirtualModelConstituentPicker(this.#host, 'vm-models', []);
        const strategyControl = resolveVirtualModelsValueControl(this.#host, modalUiSelector(this.modalId, 'vm-strategy'), modalRoot);
        this.state.originalCreateName = '';
        this.state.originalCreateStrategy = strategyControl.value;
        this.state.originalCreateModels = [];
        this.#notifyChanged();
    }

    collectSelectedModels(selector: string | Element, context?: Element): { universalId: string }[] {
        return collectVirtualModelSelection(this.#host, selector, context);
    }

    async _processModelAction(actionType: string, name: string | null, payload: JsonObject): Promise<void> {
        const normalizedAction = actionType === 'create' ? 'create' : 'update';
        await processVirtualModelAction(
            {
                host: this.#host,
                state: this.state,
                loadVirtualModelsList: (): void => this.loadVirtualModelsList(),
                closeVmEditModal: (): void => {
                    this.#host.view.modals.close(MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID);
                },
                resetCreateForm: (): void => this.#resetCreateForm(),
                updateVirtualTabs: (active: VirtualModelsPrimaryTab): void => this.updateVirtualTabs(active)
            },
            normalizedAction,
            name,
            payload
        );
    }

    async _createVirtualModelAction(): Promise<void> {
        await submitCreateVirtualModel({
            host: this.#host,
            state: this.state,
            modalId: this.modalId,
            collectSelectedModels: (selector: string | Element, context?: Element): { universalId: string }[] => this.collectSelectedModels(selector, context),
            processModelAction: (actionType: 'create' | 'update', name: string | null, payload: JsonObject): Promise<void> => this._processModelAction(actionType, name, payload)
        });
    }

    async _saveEditedVirtualModelAction(): Promise<void> {
        await submitEditedVirtualModel({
            host: this.#host,
            state: this.state,
            modalId: this.modalId,
            collectSelectedModels: (selector: string | Element, context?: Element): { universalId: string }[] => this.collectSelectedModels(selector, context),
            processModelAction: (actionType: 'create' | 'update', name: string | null, payload: JsonObject): Promise<void> => this._processModelAction(actionType, name, payload)
        });
    }

    async deleteVirtualModel(name: string): Promise<void> {
        await deleteVirtualModel(
            {
                host: this.#host,
                loadVirtualModelsList: (): void => this.loadVirtualModelsList()
            },
            name
        );
    }

    bindVirtualModelSelectors(): void {
        bindVirtualModelSelectionControls(this.#host, () => this.#notifyChanged());
    }

    #notifyChanged(): void {
        syncVirtualModelFieldState(this.#fieldState, this.state);
        this.#save?.notifyChanged();
    }
}

export { VirtualModelsManager };
