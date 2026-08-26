/* SoAI - Automation editor modal save and dirty tracking controller [frontend/assets/ts/pages/automation/controllers/AutomationEditorSaveController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { i18n } from '@core/i18n/index.ts';
import { attachBeforeCloseConfirmationGuard } from '@core/modals/closeGuard.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { showUnsavedChangesConfirmation } from '@core/modals/unsavedChangesConfirmation.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL, type SaveController } from '@core/save/public.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import { AUTOMATION_ACTION_SAVE_AUTOMATION, AUTOMATION_CONFIGURATION_MODAL_ID, type AutomationDataService, type CreateAutomationPayload } from '@features/automation/public.ts';
import { AutomationConfigurationFieldStateController } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFieldStateController.ts';
import { AUTOMATION_CONFIGURATION_PARAMETERS_UPDATED_EVENT } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationParametersController.ts';
import { AUTOMATION_CONFIGURATION_TURNS_UPDATED_EVENT } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationTurnsController.ts';
import { AUTOMATION_CONFIGURATION_WORKSPACE_UPDATED_EVENT } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationModelSettingsController.ts';
import { performAutomationEditorSave } from '@pages/automation/controllers/service.ts';

interface AutomationEditorSaveModalPort {
    getSnapshotKey(): string;
    isOpen(): boolean;
    isValid(): boolean;
    readAndValidate(): { payload: CreateAutomationPayload; editingAutomationId: string | null } | null;
    close(): void;
}

interface AutomationEditorSaveControllerDependencies {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modalPresenter: ModalPresenterApi;
    modal: AutomationEditorSaveModalPort;
    dataService: AutomationDataService;
    storage: StorageService;
    refreshData: () => Promise<void>;
    showNotification: (message: string, type?: NotificationType, duration?: number) => void;
}

class AutomationEditorSaveController {
    readonly #dependencies: AutomationEditorSaveControllerDependencies;
    readonly #modalSessionToken = new SequenceToken();
    #save: SaveController | null = null;
    #baselineSnapshotKey: string | null = null;
    #touchedByUser = false;
    #trackingAbort: AbortController | null = null;
    #fieldState: AutomationConfigurationFieldStateController | null = null;
    #removeCloseGuard: (() => void) | null = null;
    #activeChildModalIds = new Set<number>();
    #nextChildModalId = 0;
    readonly #handleTrustedFieldTouched = (event: Event): void => {
        if (event.isTrusted) {
            this.#touchedByUser = this.#fieldState?.markTouchedFromEvent(event) === true || this.#touchedByUser;
        }
        this.#fieldState?.sync();
    };
    readonly #handleTurnsTouched = (): void => {
        this.#markTouched('turns');
    };
    readonly #handleWorkspaceTouched = (): void => {
        this.#markTouched('workspace');
    };
    readonly #handleParametersTouched = (): void => {
        this.#markTouched('parameters');
    };

    constructor(dependencies: AutomationEditorSaveControllerDependencies) {
        this.#dependencies = dependencies;
    }

    dispose(): void {
        this.#save?.dispose();
        this.#save = null;
        this.#baselineSnapshotKey = null;
        this.#touchedByUser = false;
        this.#activeChildModalIds.clear();
        this.#fieldState?.clear();
        this.#fieldState = null;
        this.#removeCloseGuard?.();
        this.#removeCloseGuard = null;
        this.#trackingAbort?.abort();
        this.#trackingAbort = null;
        this.#modalSessionToken.invalidate();
    }

    begin(modal: Element): void {
        if (!(modal instanceof HTMLElement)) {
            throw new TypeError('Automation configuration modal root must be an HTMLElement');
        }
        this.dispose();
        this.#modalSessionToken.next();
        const saveButtonCandidate = this.#dependencies.requireHTMLElement(modalUiSelector(AUTOMATION_CONFIGURATION_MODAL_ID, 'save-button'), modal);
        if (!(saveButtonCandidate instanceof HTMLButtonElement)) {
            throw new Error('Automation configuration modal save button must be a button element');
        }
        if (saveButtonCandidate.dataset['action'] !== AUTOMATION_ACTION_SAVE_AUTOMATION) {
            throw new Error(`Automation configuration modal save button must use data-action="${AUTOMATION_ACTION_SAVE_AUTOMATION}"`);
        }
        this.#baselineSnapshotKey = this.#dependencies.modal.getSnapshotKey();
        this.#touchedByUser = false;
        this.#fieldState = new AutomationConfigurationFieldStateController(modal);
        this.#trackingAbort = new AbortController();
        this.#bindDirtyTracking(modal, this.#trackingAbort.signal);
        this.#attachSaveController(modal, saveButtonCandidate);
    }

    notifyChanged(): void {
        this.#save?.notifyChanged();
    }

    resetBaselineToCurrentIfUntouched(): void {
        if (!this.#dependencies.modal.isOpen() || this.#baselineSnapshotKey === null) {
            return;
        }
        if (this.#hasActiveChildModal()) {
            return;
        }
        if (this.#save?.isSaving()) {
            return;
        }
        if (this.#touchedByUser) {
            this.#fieldState?.sync();
            this.#save?.notifyChanged();
            return;
        }
        this.#baselineSnapshotKey = this.#dependencies.modal.getSnapshotKey();
        this.#fieldState?.resetBaseline();
        this.#save?.notifyChanged();
    }

    async runChildModal(operation: () => Promise<boolean>): Promise<boolean> {
        if (!this.#save || this.#save.isSaving() || this.#hasActiveChildModal()) {
            return false;
        }
        this.#nextChildModalId += 1;
        const childModalId = this.#nextChildModalId;
        this.#activeChildModalIds.add(childModalId);
        this.#save.notifyChanged();
        try {
            return await operation();
        } finally {
            this.#activeChildModalIds.delete(childModalId);
            this.#save?.notifyChanged();
        }
    }

    async requestSave(): Promise<void> {
        if (!this.#save || this.#hasActiveChildModal()) {
            return;
        }
        await this.#save.requestSave();
    }

    #bindDirtyTracking(modal: HTMLElement, signal: AbortSignal): void {
        modal.addEventListener('input', this.#handleTrustedFieldTouched, { signal, capture: true });
        modal.addEventListener('change', this.#handleTrustedFieldTouched, { signal, capture: true });
        modal.addEventListener(AUTOMATION_CONFIGURATION_TURNS_UPDATED_EVENT, this.#handleTurnsTouched, { signal });
        modal.addEventListener(AUTOMATION_CONFIGURATION_WORKSPACE_UPDATED_EVENT, this.#handleWorkspaceTouched, { signal });
        modal.addEventListener(AUTOMATION_CONFIGURATION_PARAMETERS_UPDATED_EVENT, this.#handleParametersTouched, { signal });
    }

    #markTouched(key: string): void {
        this.#touchedByUser = true;
        this.#fieldState?.markTouched(key);
        this.#fieldState?.sync();
    }

    #attachSaveController(modal: HTMLElement, saveButton: HTMLButtonElement): void {
        const save = createSaveController({
            headerContextId: 'automation:configuration-modal',
            headerPriority: SAVE_HEADER_PRIORITY_MODAL,
            requestContextLabel: 'Automation editor save',
            units: [
                {
                    id: 'automation:configuration',
                    hasChanges: () => this.#hasChanges(),
                    isValid: () => !this.#hasActiveChildModal() && (this.#dependencies.modal.isOpen() ? this.#dependencies.modal.isValid() : false),
                    save: async () => this.#performSaveAutomation()
                }
            ]
        });
        this.#save = save;
        setAriaBusy(modal, false);
        save.attach({
            resolveSaveButtons: () => [saveButton],
            busyRoots: [modal],
            autoNotifyRoot: modal,
            additionalDirtyEventNames: [AUTOMATION_CONFIGURATION_TURNS_UPDATED_EVENT, AUTOMATION_CONFIGURATION_WORKSPACE_UPDATED_EVENT, AUTOMATION_CONFIGURATION_PARAMETERS_UPDATED_EVENT]
        });
        this.#removeCloseGuard = attachBeforeCloseConfirmationGuard({
            modal,
            presenter: this.#dependencies.modalPresenter,
            modalId: AUTOMATION_CONFIGURATION_MODAL_ID,
            shouldConfirmClose: () => save.isSaving() || save.hasChanges(),
            confirmClose: async () => await this.#confirmDiscard(save)
        });
    }

    #hasChanges(): boolean {
        if (!this.#dependencies.modal.isOpen() || this.#baselineSnapshotKey === null) {
            return false;
        }
        return this.#dependencies.modal.getSnapshotKey() !== this.#baselineSnapshotKey;
    }

    #hasActiveChildModal(): boolean {
        return this.#activeChildModalIds.size > 0;
    }

    async #confirmDiscard(save: SaveController): Promise<boolean> {
        if (save.isSaving()) {
            this.#dependencies.showNotification(i18n.t('common.processing'), 'info');
            return false;
        }
        return await showUnsavedChangesConfirmation();
    }

    async #performSaveAutomation(): Promise<void> {
        if (this.#hasActiveChildModal()) {
            return;
        }
        await performAutomationEditorSave({
            modal: this.#dependencies.modal,
            modalSessionToken: this.#modalSessionToken.value,
            isModalSessionActive: (token) => this.#modalSessionToken.isActive(token),
            dataService: this.#dependencies.dataService,
            storage: this.#dependencies.storage,
            refreshData: this.#dependencies.refreshData,
            showNotification: this.#dependencies.showNotification
        });
    }
}

export { AutomationEditorSaveController };
