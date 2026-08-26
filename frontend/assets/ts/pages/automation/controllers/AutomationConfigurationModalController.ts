/* SoAI - Automation page configuration modal controller [frontend/assets/ts/pages/automation/controllers/AutomationConfigurationModalController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { ReadOnlyFileBrowserApi } from '@core/fileexplorerbrowser/types.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { AUTOMATION_CONFIGURATION_MODAL_ID, type AutomationDefinition, type AutomationMcpCatalog, type AutomationModelOption, type CreateAutomationPayload } from '@features/automation/public.ts';
import { AutomationConfigurationFormController } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFormController.ts';
import type { AutomationCreateDefaults } from '@pages/automation/state/AutomationCreateDefaultsManager.ts';

interface ModalUi {
    modal: HTMLElement;
    title: HTMLElement;
    footerCloseButton: HTMLButtonElement;
    footerEditButton: HTMLButtonElement;
    footerSaveButton: HTMLButtonElement;
}

interface ModalControllerDependencies {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modalPresenter: ModalPresenterApi;
    getIconSync: (icon: IconName, options?: IconOptions) => TrustedHtml;
}

class AutomationConfigurationModalController {
    readonly #dependencies: ModalControllerDependencies;
    readonly #modalId = AUTOMATION_CONFIGURATION_MODAL_ID;
    readonly #ui: ModalUi;
    readonly #form: AutomationConfigurationFormController;
    #editingAutomationId: string | null = null;
    #mode: 'create' | 'edit' | 'preview' = 'create';
    #modalVersion = 0;

    constructor(dependencies: ModalControllerDependencies) {
        this.#dependencies = dependencies;
        const modal = dependencies.modalPresenter.requireElement(this.#modalId);
        const footerCloseCandidate = dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'close-button'), modal);
        if (!(footerCloseCandidate instanceof HTMLButtonElement)) {
            throw new Error('Automation configuration modal close button missing');
        }
        const footerEditCandidate = dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'edit-button'), modal);
        if (!(footerEditCandidate instanceof HTMLButtonElement)) {
            throw new Error('Automation configuration modal edit button missing');
        }
        const footerSaveCandidate = dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'save-button'), modal);
        if (!(footerSaveCandidate instanceof HTMLButtonElement)) {
            throw new Error('Automation configuration modal save button missing');
        }
        this.#ui = {
            modal,
            title: dependencies.requireHTMLElement(modalUiSelector(this.#modalId, 'title'), modal),
            footerCloseButton: footerCloseCandidate,
            footerEditButton: footerEditCandidate,
            footerSaveButton: footerSaveCandidate
        };
        this.#form = new AutomationConfigurationFormController({
            requireHTMLElement: dependencies.requireHTMLElement,
            modal,
            modalPresenter: dependencies.modalPresenter,
            getIconSync: dependencies.getIconSync
        });
    }

    #applyMode(mode: 'create' | 'edit' | 'preview'): void {
        this.#mode = mode;
        this.#ui.modal.classList.toggle('automation-configuration-modal--preview', mode === 'preview');
        this.#ui.footerCloseButton.textContent = mode === 'preview' ? i18n.t('common.close') : i18n.t('automation.modal.cancel');
        this.#ui.footerEditButton.classList.toggle('u-hidden', mode !== 'preview');
        this.#ui.footerSaveButton.classList.toggle('u-hidden', mode === 'preview');
        this.#form.setReadOnlyMode(mode === 'preview');
    }

    isOpen(): boolean {
        return this.#dependencies.modalPresenter.isOpen(this.#modalId);
    }

    getEditingAutomationId(): string | null {
        return this.#editingAutomationId;
    }

    setAvailableModels(models: readonly AutomationModelOption[]): void {
        this.#form.setAvailableModels(models);
    }

    setMcpCatalog(catalog: AutomationMcpCatalog): void {
        this.#form.setMcpCatalog(catalog);
    }

    openCreate(defaults: { startLocal: string; timezone: string; createDefaults: AutomationCreateDefaults; currentWorkspacePath: string }): void {
        this.#modalVersion += 1;
        this.#editingAutomationId = null;
        this.#ui.title.textContent = i18n.t('automation.modal.createTitle');
        this.#form.setCreateValues(defaults);
        this.#applyMode('create');
        this.#dependencies.modalPresenter.open(this.#modalId);
    }

    openEdit(automation: AutomationDefinition, currentWorkspacePath: string): void {
        this.#modalVersion += 1;
        this.#editingAutomationId = automation.id;
        this.#ui.title.textContent = i18n.t('automation.modal.editTitle');
        this.#form.setEditValues(automation, currentWorkspacePath);
        this.#applyMode('edit');
        this.#dependencies.modalPresenter.open(this.#modalId);
    }

    openPreview(automation: AutomationDefinition, currentWorkspacePath: string): void {
        this.#modalVersion += 1;
        this.#editingAutomationId = automation.id;
        this.#ui.title.textContent = i18n.t('automation.modal.previewTitle');
        this.#form.setEditValues(automation, currentWorkspacePath);
        this.#applyMode('preview');
        this.#dependencies.modalPresenter.open(this.#modalId);
    }

    enterEditMode(): void {
        if (this.#mode !== 'preview') {
            return;
        }
        this.#ui.title.textContent = i18n.t('automation.modal.editTitle');
        this.#applyMode('edit');
    }

    close(): void {
        this.#modalVersion += 1;
        this.#dependencies.modalPresenter.close(this.#modalId, { reason: 'automation:configuration:close' });
    }

    addTurn(): void {
        this.#form.addTurn();
    }

    removeTurn(turnIndex: string | null): void {
        this.#form.removeTurn(turnIndex);
    }

    async openWorkspaceModal(api: ReadOnlyFileBrowserApi, allowManualAbsoluteSelectionOutsideRoot: boolean): Promise<boolean> {
        if (!this.isOpen()) {
            return false;
        }
        const modalVersion = this.#modalVersion;
        return await this.#form.openWorkspaceModal(api, allowManualAbsoluteSelectionOutsideRoot, () => this.#canApplyChildModal(modalVersion));
    }

    async openParametersModal(): Promise<boolean> {
        if (!this.isOpen()) {
            return false;
        }
        const modalVersion = this.#modalVersion;
        return await this.#form.openParametersModal(() => this.#canApplyChildModal(modalVersion));
    }

    #canApplyChildModal(modalVersion: number): boolean {
        return this.#modalVersion === modalVersion && this.isOpen() && this.#mode !== 'preview';
    }

    getSnapshotKey(): string {
        return this.#form.getSnapshotKey();
    }

    isValid(): boolean {
        return this.#form.isValid();
    }

    readAndValidate(): { payload: CreateAutomationPayload; editingAutomationId: string | null } | null {
        const payload = this.#form.readAndValidate();
        if (!payload) {
            return null;
        }
        return { editingAutomationId: this.#editingAutomationId, payload };
    }

    destroy(): void {
        this.#form.destroy();
    }
}

export { AutomationConfigurationModalController };
