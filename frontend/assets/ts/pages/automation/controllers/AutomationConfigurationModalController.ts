/* SoAI - Automation page configuration modal controller [frontend/assets/ts/pages/automation/controllers/AutomationConfigurationModalController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { narrowButton } from '@core/dom/narrowElement.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { ReadOnlyFileBrowserApi } from '@core/fileexplorerbrowser/types.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { AUTOMATION_CONFIGURATION_MODAL_ID, type AutomationDefinitionResponse, type AutomationMcpCatalogResponse, type AutomationModelOption, type AutomationSchedulePreviewResponse, type AutomationSchedulePreviewRequest, type CreateAutomationRequest, type UpdateAutomationRequest } from '@features/automation/public.ts';
import { AutomationConfigurationFormController, type AutomationCreateValues } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFormController.ts';
import { buildAutomationCreatePayload, buildAutomationUpdatePayload, formatAutomationDefinitionChangeFields, listChangedDefinitionFields, listChangedDraftFields, rebaseAutomationEditorDraft, type AutomationEditorDraft, type AutomationEditorValidDraft } from '@pages/automation/controllers/configurationmodal/AutomationEditorDraftDomain.ts';
import { AutomationEditorStatusController, type AutomationEditorFreezeReason, type AutomationEditorPrerequisitesState } from '@pages/automation/controllers/configurationmodal/AutomationEditorStatusController.ts';
import type { AutomationCalendarSettings } from '@pages/automation/types.ts';

type AutomationEditorMode = 'create' | 'edit' | 'preview';

type AutomationEditorSubmission = { type: 'create'; payload: CreateAutomationRequest } | { type: 'update'; automationId: string; payload: UpdateAutomationRequest; expectedRevision: string };

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
    previewSchedule: (input: AutomationSchedulePreviewRequest, signal?: AbortSignal) => Promise<AutomationSchedulePreviewResponse>;
    getCalendarSettings: () => AutomationCalendarSettings;
}

interface AutomationEditorBaseline {
    definition: AutomationDefinitionResponse | null;
    draft: AutomationEditorDraft;
}

const formatModeTitle = (mode: AutomationEditorMode): string => {
    switch (mode) {
        case 'create':
            return i18n.t('automation.modal.createTitle');
        case 'edit':
            return i18n.t('automation.modal.editTitle');
        case 'preview':
            return i18n.t('automation.modal.previewTitle');
    }
};

class AutomationConfigurationModalController {
    readonly #dependencies: ModalControllerDependencies;
    readonly #modalId = AUTOMATION_CONFIGURATION_MODAL_ID;
    readonly #ui: ModalUi;
    readonly #form: AutomationConfigurationFormController;
    readonly #status: AutomationEditorStatusController;
    #mode: AutomationEditorMode = 'create';
    #modalVersion = 0;
    #baseline: AutomationEditorBaseline | null = null;
    #pendingConflict: AutomationDefinitionResponse | null = null;

    constructor(dependencies: ModalControllerDependencies) {
        this.#dependencies = dependencies;
        const modal = dependencies.modalPresenter.requireElement(this.#modalId);
        const requireElement = (token: string): HTMLElement => dependencies.requireHTMLElement(modalUiSelector(this.#modalId, token), modal);
        this.#ui = {
            modal,
            title: requireElement('title'),
            footerCloseButton: narrowButton(requireElement('close-button'), 'Automation configuration modal close button'),
            footerEditButton: narrowButton(requireElement('edit-button'), 'Automation configuration modal edit button'),
            footerSaveButton: narrowButton(requireElement('save-button'), 'Automation configuration modal save button')
        };
        this.#form = new AutomationConfigurationFormController({
            requireHTMLElement: dependencies.requireHTMLElement,
            modal,
            modalPresenter: dependencies.modalPresenter,
            getIconSync: dependencies.getIconSync,
            previewSchedule: dependencies.previewSchedule,
            getCalendarSettings: dependencies.getCalendarSettings
        });
        this.#status = new AutomationEditorStatusController({ requireHTMLElement: dependencies.requireHTMLElement, modal, formRegion: this.#form.getFormRegion() });
    }

    getForm(): AutomationConfigurationFormController {
        return this.#form;
    }

    isOpen(): boolean {
        return this.#dependencies.modalPresenter.isOpen(this.#modalId);
    }

    isEditable(): boolean {
        return this.isOpen() && this.#mode !== 'preview' && this.#status.arePrerequisitesReady() && !this.hasPendingConflict();
    }

    arePrerequisitesReady(): boolean {
        return this.#status.arePrerequisitesReady();
    }

    hasPendingConflict(): boolean {
        return this.#pendingConflict !== null;
    }

    beginOpen(mode: AutomationEditorMode): void {
        this.#modalVersion += 1;
        this.#baseline = null;
        this.#pendingConflict = null;
        this.#status.reset();
        this.#applyMode(mode);
        this.#status.setPrerequisitesState({ type: 'loading' });
        this.#dependencies.modalPresenter.open(this.#modalId);
    }

    setPrerequisitesState(state: AutomationEditorPrerequisitesState): void {
        this.#status.setPrerequisitesState(state);
    }

    setToolsUnavailable(unavailable: boolean): void {
        this.#status.setToolsUnavailable(unavailable);
    }

    setFrozen(reason: AutomationEditorFreezeReason, frozen: boolean): void {
        this.#status.setFrozen(reason, frozen);
    }

    setAvailableModels(models: readonly AutomationModelOption[]): void {
        this.#form.setAvailableModels(models);
    }

    setMcpCatalog(catalog: AutomationMcpCatalogResponse): void {
        this.#form.setMcpCatalog(catalog);
    }

    applyCreate(values: AutomationCreateValues): void {
        this.#form.setCreateValues(values);
        this.#adoptBase(null);
    }

    applyDefinition(definition: AutomationDefinitionResponse, currentWorkspacePath: string): void {
        this.#form.setEditValues(definition, currentWorkspacePath);
        this.#adoptBase(definition);
    }

    enterEditMode(): void {
        if (this.#mode === 'preview') {
            this.#applyMode('edit');
        }
    }

    close(): void {
        this.#modalVersion += 1;
        this.#dependencies.modalPresenter.close(this.#modalId, { reason: 'automation:configuration:close' });
    }

    dismiss(): void {
        this.#modalVersion += 1;
        this.#dependencies.modalPresenter.close(this.#modalId, { force: true, reason: 'automation:configuration:dismiss' });
    }

    addTurn(): void {
        if (this.isEditable()) {
            this.#form.addTurn();
        }
    }

    removeTurn(turnIndex: string | null): void {
        if (this.isEditable()) {
            this.#form.removeTurn(turnIndex);
        }
    }

    async openWorkspaceModal(api: ReadOnlyFileBrowserApi, signal?: AbortSignal): Promise<boolean> {
        if (!this.isOpen()) {
            return false;
        }
        const modalVersion = this.#modalVersion;
        return await this.#form.openWorkspaceModal(api, () => this.#canApplyChildModal(modalVersion), signal);
    }

    async openParametersModal(signal?: AbortSignal): Promise<boolean> {
        if (!this.isOpen()) {
            return false;
        }
        const modalVersion = this.#modalVersion;
        return await this.#form.openParametersModal(() => this.#canApplyChildModal(modalVersion), signal);
    }

    hasChanges(): boolean {
        return this.isOpen() && this.#baseline !== null && listChangedDraftFields(this.#baseline.draft, this.#form.readDraft()).length > 0;
    }

    readSubmission(validDraft: AutomationEditorValidDraft): AutomationEditorSubmission | null {
        const baseline = this.#baseline;
        if (!this.isEditable() || baseline === null) {
            return null;
        }
        if (this.#mode === 'create' || baseline.definition === null) {
            return { type: 'create', payload: buildAutomationCreatePayload(validDraft) };
        }
        return {
            type: 'update',
            automationId: baseline.definition.id,
            payload: buildAutomationUpdatePayload(listChangedDraftFields(baseline.draft, validDraft), validDraft),
            expectedRevision: baseline.definition.revision
        };
    }

    showConflict(latest: AutomationDefinitionResponse): void {
        const baseline = this.#baseline;
        if (baseline === null || baseline.definition === null) {
            throw new Error('Automation conflict requires an edited definition');
        }
        this.#pendingConflict = latest;
        const remoteFields = listChangedDefinitionFields(baseline.definition, latest);
        const localFields = listChangedDraftFields(baseline.draft, this.#form.readDraft());
        const lines = [i18n.t('automation.modal.conflict.message')];
        if (remoteFields.length > 0) lines.push(i18n.t('automation.modal.conflict.remoteChanges', { fields: formatAutomationDefinitionChangeFields(remoteFields) }));
        if (localFields.length > 0) lines.push(i18n.t('automation.modal.conflict.localChanges', { fields: formatAutomationDefinitionChangeFields(localFields) }));
        this.#status.showConflict(lines.join('\n'));
    }

    keepChangesAfterConflict(adoptBaseline: () => void): boolean {
        const latest = this.#pendingConflict;
        const baseline = this.#baseline;
        if (latest === null || baseline === null) {
            return false;
        }
        const original = baseline.draft;
        const local = this.#form.readDraft();
        this.#form.setEditValues(latest);
        this.#adoptBase(latest);
        const latestDraft = this.#form.readDraft();
        adoptBaseline();
        this.#form.applyDraft(rebaseAutomationEditorDraft(original, local, latestDraft));
        return true;
    }

    takePendingConflict(): AutomationDefinitionResponse | null {
        const latest = this.#pendingConflict;
        this.#pendingConflict = null;
        this.#status.showConflict(null);
        return latest;
    }

    endSession(): void {
        this.#modalVersion += 1;
        this.#form.endSession();
    }

    destroy(): void {
        this.endSession();
        this.#form.destroy();
    }

    #adoptBase(definition: AutomationDefinitionResponse | null): void {
        this.#pendingConflict = null;
        this.#status.showConflict(null);
        this.#baseline = { definition, draft: this.#form.readDraft() };
    }

    #applyMode(mode: AutomationEditorMode): void {
        this.#mode = mode;
        this.#ui.title.textContent = formatModeTitle(mode);
        this.#ui.modal.classList.toggle('automation-configuration-modal--preview', mode === 'preview');
        this.#ui.footerCloseButton.textContent = mode === 'preview' ? i18n.t('common.close') : i18n.t('automation.modal.cancel');
        this.#ui.footerEditButton.classList.toggle('u-hidden', mode !== 'preview');
        this.#ui.footerSaveButton.classList.toggle('u-hidden', mode === 'preview');
        this.#form.setReadOnlyMode(mode === 'preview');
    }

    #canApplyChildModal(modalVersion: number): boolean {
        return this.#modalVersion === modalVersion && this.isEditable();
    }
}

export { AutomationConfigurationModalController };
export type { AutomationEditorMode, AutomationEditorSubmission };
