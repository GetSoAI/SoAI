/* SoAI - Models feature rename model modal manager [frontend/assets/ts/features/models/modals/renamemodal/RenameModelModalManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { requireButtonElement, requireInputElement } from '@core/dom/typedElements.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { i18n } from '@core/i18n/index.ts';
import { LifecycleScope } from '@core/lifecycle/lifecycleScope.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { resolveModelSourceName } from '@core/models/modelIdentity.ts';
import type { SaveController } from '@core/save/public.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { MODELS_RENAME_MODEL_MODAL_ID } from '@features/models/modals/constants.ts';
import { clearRenameFormFields } from '@features/models/modals/renamemodal/effects.ts';
import { createRenameModelFieldStateTracker, syncRenameModelFieldState } from '@features/models/modals/renamemodal/fieldState.ts';
import { hasRenameFormChanges, resolveCurrentModelAlias, resolveModelUniversalId } from '@features/models/modals/renamemodal/mappers.ts';
import { createModelModalSaveSession } from '@features/models/modals/saveSession.ts';
import type { RenameModelModalHost, RenameModelModalManagerDependencies, RenameModelModalState } from '@features/models/modals/renamemodal/types.ts';

class RenameModelModalManager {
    readonly modalId = MODELS_RENAME_MODEL_MODAL_ID;
    readonly #host: RenameModelModalHost;
    readonly state: RenameModelModalState;
    #fieldState: FieldStateTracker | null = null;
    #save: SaveController | null = null;
    #saveSessionDispose: (() => void) | null = null;
    #listenersScope: LifecycleScope = new LifecycleScope();
    #modalSession = 0;

    readonly #onSaveClick = (): void => {
        terminateHandledPromise(this.requestSave());
    };

    constructor({ host }: RenameModelModalManagerDependencies) {
        this.#host = host;
        this.state = {
            selectedModel: null,
            originalAlias: ''
        };
    }

    #resetListeners(): void {
        this.#listenersScope.abort('rename-model-modal-reset');
    }

    #disposeSaveWiring(): void {
        this.#fieldState?.clearAll();
        this.#fieldState = null;
        this.#saveSessionDispose?.();
        this.#saveSessionDispose = null;
        this.#save = null;
    }

    #clearModalState(clearFields: boolean): void {
        this.#modalSession += 1;
        if (clearFields) {
            const modalRoot = this.#host.modals.requireElement(this.modalId);
            clearRenameFormFields(this.#host, modalRoot);
        }
        this.#disposeSaveWiring();
        this.#resetListeners();
        this.state.selectedModel = null;
        this.state.originalAlias = '';
    }

    showRenameModal(model: ModelRecord): void {
        const universalId = resolveModelUniversalId(model);
        if (!universalId) {
            throw new Error('RenameModelModalManager requires a model universalId');
        }
        const sourceModelName = resolveModelSourceName(model);
        if (!sourceModelName) {
            throw new Error('RenameModelModalManager requires a source model identifier');
        }
        this.#resetListeners();
        this.#disposeSaveWiring();
        this.#modalSession += 1;
        const modalSession = this.#modalSession;
        const { signal } = this.#listenersScope.begin('rename-model-modal-open');

        const modalRoot = this.#host.modals.requireElement(this.modalId);
        const modalTitle = this.#host.requireHTMLElement(modalUiSelector(this.modalId, 'title'), modalRoot);
        const sourceName = this.#host.requireHTMLElement(modalUiSelector(this.modalId, 'source-model-id'), modalRoot);
        const aliasInput = requireInputElement(this.#host, modalUiSelector(this.modalId, 'alias-input'), 'RenameModelModalManager alias input', modalRoot);
        const saveButton = requireButtonElement(this.#host, modalUiSelector(this.modalId, 'save'), 'RenameModelModalManager save button', modalRoot);

        this.state.selectedModel = model;
        this.state.originalAlias = resolveCurrentModelAlias(model);

        this.#host.updateText(modalTitle, i18n.t('models.modal.rename.title'));
        this.#host.updateText(sourceName, sourceModelName);
        this.#host.setUIValue(aliasInput, this.state.originalAlias, { attribute: 'value' });
        this.#fieldState = createRenameModelFieldStateTracker(modalRoot, aliasInput, () => this.state.originalAlias);

        const saveSession = createModelModalSaveSession({
            host: this.#host,
            modal: modalRoot,
            modalId: this.modalId,
            presenter: this.#host.modals,
            headerContextId: 'rename-model',
            requestContextLabel: 'Rename model save',
            resolveSaveButtons: () => [saveButton],
            hasChanges: () => hasRenameFormChanges(readTrimmedInputValue(aliasInput), this.state.originalAlias),
            save: async () => await this.#applyRenameSave(modalSession),
            busyRoots: [modalRoot]
        });
        this.#save = saveSession.save;
        this.#saveSessionDispose = saveSession.dispose;

        const updateModalState = (): void => {
            const aliasValue = readTrimmedInputValue(aliasInput);
            this.#host.updateText(modalTitle, aliasValue ? i18n.t('models.modal.rename.titlePreview', { alias: aliasValue }) : i18n.t('models.modal.rename.title'));
            syncRenameModelFieldState(this.#fieldState);
            this.#save?.notifyChanged();
        };
        aliasInput.addEventListener('input', updateModalState, { signal });
        saveButton.addEventListener('click', this.#onSaveClick, { signal });
        updateModalState();

        this.#host.modals.open(this.modalId);
    }

    async requestSave(): Promise<void> {
        if (!this.#save) {
            throw new Error('RenameModelModalManager requestSave requires an active SaveController');
        }
        await this.#save.requestSave();
    }

    async #applyRenameSave(modalSession: number): Promise<void> {
        const selectedModel = this.state.selectedModel;
        if (!selectedModel) {
            throw new Error('RenameModelModalManager save requires an active model');
        }
        const universalId = resolveModelUniversalId(selectedModel);
        if (!universalId) {
            throw new Error('RenameModelModalManager requires a model universalId');
        }
        const modalRoot = this.#host.modals.requireElement(this.modalId);
        const aliasInput = requireInputElement(this.#host, modalUiSelector(this.modalId, 'alias-input'), 'RenameModelModalManager alias input', modalRoot);
        const nextAlias = readTrimmedInputValue(aliasInput);
        const isAliasUpdate = Boolean(nextAlias);
        try {
            if (isAliasUpdate) {
                await this.#host.runWithBoundary('models:renameModel', async () =>
                    this.#host.modelActions.updateAlias(universalId, {
                        displayName: nextAlias,
                        description: typeof selectedModel.description === 'string' ? selectedModel.description : null
                    })
                );
            } else {
                await this.#host.runWithBoundary('models:removeModelAlias', async () => this.#host.modelActions.removeAlias(universalId));
            }
            if (modalSession === this.#modalSession) {
                await this.#host.runWithBoundary('models:refreshRenamedModelCollection', async () => this.#host.refreshModelsCollection());
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            if (modalSession === this.#modalSession) {
                if (isAliasUpdate) {
                    this.#host.showNotification(i18n.t('models.notifications.aliasUpdateFailed'), 'error');
                } else {
                    this.#host.showNotification(i18n.t('models.notifications.aliasRemoveFailed'), 'error');
                }
            }
            throw runtimeError;
        }
        if (modalSession !== this.#modalSession) {
            return;
        }
        if (isAliasUpdate) {
            this.#host.showNotification(i18n.t('models.notifications.aliasUpdateSuccess', { model: resolveModelSourceName(selectedModel) }), 'success');
        } else {
            this.#host.showNotification(i18n.t('models.notifications.aliasRemoveSuccess', { model: resolveModelSourceName(selectedModel) }), 'success');
        }
        this.state.originalAlias = nextAlias;
        syncRenameModelFieldState(this.#fieldState);
        this.#save?.notifyChanged();
        if (readTrimmedInputValue(aliasInput) !== nextAlias) {
            return;
        }
        this.#host.modals.close(this.modalId);
    }

    onModalClosed(): void {
        this.#clearModalState(true);
    }

    disposeForPageDestroy(): void {
        this.#clearModalState(true);
    }
}

export { RenameModelModalManager };
export type { RenameModelModalHost };
