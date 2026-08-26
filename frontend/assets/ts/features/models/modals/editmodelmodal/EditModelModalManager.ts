/* SoAI - Models feature edit model modal manager [frontend/assets/ts/features/models/modals/editmodelmodal/EditModelModalManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { requireButtonElement } from '@core/dom/typedElements.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { LifecycleScope } from '@core/lifecycle/lifecycleScope.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { resolveModelSourceName } from '@core/models/modelIdentity.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import type { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import type { SaveController } from '@core/save/public.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { parseOpenAICapabilityToggleRequest, setOpenAICapabilityControlsBusy } from '@features/models/capabilities/openaiCapabilityDom.ts';
import { createOpenAICapabilityOverrideState, hasOpenAICapabilityOverrideChanges, saveOpenAICapabilityOverrideState, setOpenAICapabilityOverrideEnabled, type OpenAICapabilityOverrideState } from '@features/models/capabilities/openaiCapabilityState.ts';
import { MODELS_EDIT_MODEL_MODAL_ID } from '@features/models/modals/constants.ts';
import { bindEditModelModalActions } from '@features/models/modals/editmodelmodal/actionBindings.ts';
import { deleteFromEditModelModal, navigateFromEditModelModal, renameFromEditModelModal } from '@features/models/modals/editmodelmodal/actionFlow.ts';
import { createEditModelEnabledState, hasEditModelEnabledChanges, parseEditModelEnabledToggleRequest, populateEditModelEnabledControl, saveEditModelEnabledState, setEditModelEnabled, setEditModelEnabledControlBusy, type EditModelEnabledState } from '@features/models/modals/editmodelmodal/enabledControl.ts';
import { clearEditModelModal, copyEditModelSourceName, populateEditModelCapabilities, updateEditModelDeleteVisibility } from '@features/models/modals/editmodelmodal/effects.ts';
import { createEditModelFieldStateTracker, syncEditModelFieldState } from '@features/models/modals/editmodelmodal/fieldState.ts';
import { createModelModalSaveSession } from '@features/models/modals/saveSession.ts';
import type { EditModelModalHost, EditModelModalManagerDependencies } from '@features/models/modals/editmodelmodal/types.ts';

class EditModelModalManager {
    readonly modalId = MODELS_EDIT_MODEL_MODAL_ID;
    readonly #host: EditModelModalHost;
    #listenersScope: LifecycleScope = new LifecycleScope();
    #selectedModel: ModelRecord | null = null;
    #capabilityState: OpenAICapabilityOverrideState | null = null;
    #enabledState: EditModelEnabledState | null = null;
    #fieldState: FieldStateTracker | null = null;
    #save: SaveController | null = null;
    #saveSessionDispose: (() => void) | null = null;
    #modalSession = 0;

    constructor({ host }: EditModelModalManagerDependencies) {
        this.#host = host;
    }

    #resetListeners(): void {
        this.#listenersScope.abort('edit-model-modal-reset');
    }

    #requireSelectedModel(actionName: string): ModelRecord {
        const selectedModel = this.#selectedModel;
        if (!selectedModel) {
            throw new Error(`${actionName} requires an active model`);
        }
        return selectedModel;
    }

    readonly #onCopySourceClick = (): void => {
        terminateHandledPromise(
            this.#host.view.runWithBoundary('models:copyModelSourceName', async () => {
                await copyEditModelSourceName(this.#host, this.#requireSelectedModel('EditModelModalManager copy source name'));
            })
        );
    };

    readonly #onViewInfoClick = (): void => {
        terminateHandledPromise(navigateFromEditModelModal(this.#host.view, this.modalId, this.#save, this.#requireSelectedModel('EditModelModalManager view model info'), { tab: 'overview' }));
    };

    readonly #onTestModelClick = (): void => {
        terminateHandledPromise(navigateFromEditModelModal(this.#host.view, this.modalId, this.#save, this.#requireSelectedModel('EditModelModalManager test model'), { action: 'test' }));
    };

    readonly #onEditParametersClick = (): void => {
        terminateHandledPromise(navigateFromEditModelModal(this.#host.view, this.modalId, this.#save, this.#requireSelectedModel('EditModelModalManager edit parameters'), { tab: 'parameters' }));
    };

    readonly #onRenameClick = (): void => {
        terminateHandledPromise(renameFromEditModelModal(this.#host.view, this.modalId, this.#save, this.#requireSelectedModel('EditModelModalManager rename model')));
    };

    readonly #onDeleteClick = (): void => {
        terminateHandledPromise(deleteFromEditModelModal(this.#host.view, this.modalId, this.#save, this.#requireSelectedModel('EditModelModalManager delete model')));
    };

    readonly #onSaveClick = (): void => {
        terminateHandledPromise(this.requestSave());
    };

    #disposeSaveWiring(): void {
        this.#fieldState?.clearAll();
        this.#fieldState = null;
        this.#saveSessionDispose?.();
        this.#saveSessionDispose = null;
        this.#save = null;
    }

    async showEditModelModal(model: ModelRecord): Promise<void> {
        const sourceModelName = resolveModelSourceName(model);
        if (!sourceModelName) {
            throw new Error('EditModelModalManager requires a source model identifier');
        }
        this.#resetListeners();
        this.#disposeSaveWiring();
        this.#modalSession += 1;
        const modalSession = this.#modalSession;
        const { signal } = this.#listenersScope.begin('edit-model-modal-open');
        await this.#host.operations.ensureCapabilityManifestReady();
        if (modalSession !== this.#modalSession) {
            return;
        }
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        const modalTitle = this.#host.view.requireHTMLElement(modalUiSelector(this.modalId, 'title'), modalRoot);
        const sourceName = this.#host.view.requireHTMLElement(modalUiSelector(this.modalId, 'source-model-id'), modalRoot);
        const saveButton = requireButtonElement(this.#host.view, modalUiSelector(this.modalId, 'save'), 'EditModelModalManager save button', modalRoot);
        const universalId = toTrimmedStringOrNull(model.universalId) ?? '';
        if (!universalId) {
            throw new Error('EditModelModalManager requires model.universalId for capability overrides');
        }

        this.#selectedModel = model;
        this.#capabilityState = createOpenAICapabilityOverrideState(model, universalId);
        this.#enabledState = createEditModelEnabledState(model, universalId);
        this.#fieldState = createEditModelFieldStateTracker(modalRoot);
        this.#host.view.updateText(modalTitle, i18n.t('models.modal.edit.title'));
        this.#host.view.updateText(sourceName, sourceModelName);
        this.#renderModalState(modalRoot);

        const saveSession = createModelModalSaveSession({
            host: this.#host.view,
            modal: modalRoot,
            modalId: this.modalId,
            presenter: this.#host.view.modals,
            headerContextId: 'edit-model',
            saveUnitId: 'edit-model-settings',
            requestContextLabel: 'Edit model save',
            resolveSaveButtons: () => [saveButton],
            hasChanges: () => hasOpenAICapabilityOverrideChanges(this.#capabilityState) || hasEditModelEnabledChanges(this.#enabledState),
            save: async () => await this.#applySettingsSave(modalSession),
            onBusyChange: (busy: boolean) => {
                this.#host.view.setModalBusy(modalRoot, busy);
                setOpenAICapabilityControlsBusy(modalRoot, busy);
                setEditModelEnabledControlBusy(modalRoot, busy);
            }
        });
        this.#save = saveSession.save;
        this.#saveSessionDispose = saveSession.dispose;

        bindEditModelModalActions({
            root: modalRoot,
            signal,
            onCopySource: this.#onCopySourceClick,
            onViewInfo: this.#onViewInfoClick,
            onTestModel: this.#onTestModelClick,
            onEditParameters: this.#onEditParametersClick,
            onRename: this.#onRenameClick,
            onDelete: this.#onDeleteClick,
            onSave: this.#onSaveClick,
            onEnabledChange: (actionElement: HTMLElement): void => this.#handleEnabledChange(actionElement, modalRoot),
            onCapabilityChange: (actionElement: HTMLElement): void => this.#handleCapabilityChange(actionElement, modalRoot)
        });
        this.#host.view.modals.open(this.modalId);
    }

    #renderModalState(modalRoot: HTMLElement): void {
        const selectedModel = this.#selectedModel;
        const state = this.#capabilityState;
        const enabledState = this.#enabledState;
        if (!selectedModel || !state || !enabledState) {
            throw new Error('EditModelModalManager rendering requires an active model');
        }
        populateEditModelEnabledControl(this.#host.view, selectedModel, enabledState, modalRoot);
        populateEditModelCapabilities(this.#host, selectedModel, state, modalRoot);
        updateEditModelDeleteVisibility(this.#host, selectedModel, modalRoot);
        syncEditModelFieldState(this.#fieldState, enabledState);
        setOpenAICapabilityControlsBusy(modalRoot, this.#save?.isSaving() === true);
        setEditModelEnabledControlBusy(modalRoot, this.#save?.isSaving() === true);
    }

    #handleEnabledChange(toggle: HTMLElement, modalRoot: HTMLElement): void {
        if (!this.#enabledState || this.#save?.isSaving() || toggle.dataset['busy'] === 'true') {
            return;
        }
        setEditModelEnabled(this.#enabledState, parseEditModelEnabledToggleRequest(toggle));
        this.#renderModalState(modalRoot);
        this.#save?.notifyChanged();
    }

    #handleCapabilityChange(toggle: HTMLElement, modalRoot: HTMLElement): void {
        if (!this.#capabilityState || this.#save?.isSaving() || toggle.dataset['toggleLocked'] === 'true' || toggle.getAttribute('aria-disabled') === 'true' || toggle.dataset['busy'] === 'true') {
            return;
        }
        const request = parseOpenAICapabilityToggleRequest(toggle);
        setOpenAICapabilityOverrideEnabled(this.#capabilityState, request.category, request.token, request.enabled);
        this.#renderModalState(modalRoot);
        this.#save?.notifyChanged();
    }

    async requestSave(): Promise<void> {
        if (!this.#save) {
            throw new Error('EditModelModalManager requestSave requires an active SaveController');
        }
        await this.#save.requestSave();
    }

    async #applySettingsSave(modalSession: number): Promise<void> {
        const selectedModel = this.#selectedModel;
        const state = this.#capabilityState;
        const enabledState = this.#enabledState;
        if (!selectedModel || !state || !enabledState) {
            throw new Error('EditModelModalManager save requires an active model');
        }
        const capabilitiesChanged = hasOpenAICapabilityOverrideChanges(state);
        const enabledChanged = hasEditModelEnabledChanges(enabledState);
        const updatedModel = await this.#host.view.runWithBoundary('models:saveEditModelSettings', async (): Promise<ModelRecord> => {
            const capabilityModel = await saveOpenAICapabilityOverrideState({
                api: this.#host.operations.api,
                model: selectedModel,
                state
            });
            return await saveEditModelEnabledState({
                api: this.#host.operations.api,
                model: capabilityModel,
                state: enabledState
            });
        });
        if (modalSession !== this.#modalSession) {
            return;
        }
        this.#selectedModel = updatedModel;
        if (capabilitiesChanged && enabledChanged) {
            this.#host.view.showNotification(i18n.t('models.modal.edit.saveSuccess'), 'success');
        } else if (enabledChanged) {
            this.#host.view.showNotification(i18n.t('modelDetail.notifications.enabledUpdated'), 'success');
        } else if (capabilitiesChanged) {
            this.#host.view.showNotification(i18n.t('modelDetail.notifications.capabilitiesUpdated'), 'success');
        }
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        this.#renderModalState(modalRoot);
        this.#save?.notifyChanged();
        try {
            await this.#host.operations.refreshModelsCollection();
        } catch (error) {
            errorHandler.handleError(ensureError(error), { context: 'EditModelModalManager.refreshSavedModelCollection' });
        }
        if (modalSession !== this.#modalSession) {
            return;
        }
        this.#renderModalState(modalRoot);
        this.#save?.notifyChanged();
    }

    onModalClosed(): void {
        this.#modalSession += 1;
        this.#disposeSaveWiring();
        this.#resetListeners();
        const modalRoot = this.#host.view.modals.requireElement(this.modalId);
        clearEditModelModal(this.#host, modalRoot);
        this.#selectedModel = null;
        this.#capabilityState = null;
        this.#enabledState = null;
    }

    disposeForPageDestroy(): void {
        this.onModalClosed();
    }
}

export { EditModelModalManager };
export type { EditModelModalHost };
