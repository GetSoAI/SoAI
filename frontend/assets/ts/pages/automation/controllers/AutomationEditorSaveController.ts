/* SoAI - Automation editor modal save and dirty tracking controller [frontend/assets/ts/pages/automation/controllers/AutomationEditorSaveController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { attachBeforeCloseConfirmationGuard } from '@core/modals/closeGuard.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { showUnsavedChangesConfirmation } from '@core/modals/unsavedChangesConfirmation.ts';
import { createExclusiveSaveAdmission, createSaveController, SAVE_HEADER_PRIORITY_MODAL, type SaveController, type SaveUnitResult } from '@core/save/public.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import { AUTOMATION_ACTION_SAVE_AUTOMATION, type AutomationDataService, type AutomationDefinitionResponse } from '@features/automation/public.ts';
import { refreshAfterAutomationChange } from '@pages/automation/controllers/AutomationMutationCompletionDomain.ts';
import type { AutomationConfigurationModalController } from '@pages/automation/controllers/AutomationConfigurationModalController.ts';
import { AutomationConfigurationFieldStateController } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFieldStateController.ts';
import { AUTOMATION_CONFIGURATION_PARAMETERS_UPDATED_EVENT } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationParametersController.ts';
import { AUTOMATION_CONFIGURATION_SCHEDULE_PREVIEW_EVENT } from '@pages/automation/controllers/configurationmodal/AutomationSchedulePreviewController.ts';
import { AUTOMATION_CONFIGURATION_TURNS_UPDATED_EVENT } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationTurnsController.ts';
import { AUTOMATION_CONFIGURATION_WORKSPACE_UPDATED_EVENT } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationModelSettingsController.ts';
import { notifyAutomationEditorSaveFailure, submitAutomationEditorSubmission, type AutomationEditorSaveOutcome } from '@pages/automation/controllers/AutomationEditorSubmissionDomain.ts';
import { requireActionButton } from '@pages/automation/dom.ts';
import { saveAutomationCreateDefaults } from '@pages/automation/state/AutomationCreateDefaultsManager.ts';

interface AutomationEditorSaveControllerDependencies {
    modalPresenter: ModalPresenterApi;
    modal: AutomationConfigurationModalController;
    dataService: AutomationDataService;
    storage: StorageService;
    refreshData: () => Promise<void>;
    isPageDisposed: () => boolean;
    showNotification: (message: string, type?: NotificationType, duration?: number) => void;
}

class AutomationEditorSaveController {
    readonly #dependencies: AutomationEditorSaveControllerDependencies;
    readonly #modalSessionToken = new SequenceToken();
    #save: SaveController | null = null;
    #trackingAbort: AbortController | null = null;
    #fieldState: AutomationConfigurationFieldStateController | null = null;
    #removeCloseGuard: (() => void) | null = null;
    readonly #childAdmission = createExclusiveSaveAdmission();
    #childLease: { token: number; controller: AbortController; release: () => void } | null = null;
    readonly #handleTrustedFieldTouched = (event: Event): void => {
        if (event.isTrusted) {
            this.#fieldState?.markTouchedFromEvent(event);
        }
        this.#fieldState?.sync();
    };
    readonly #handleTurnsTouched = (): void => this.#markTouched('turns');
    readonly #handleWorkspaceTouched = (): void => this.#markTouched('workspace');
    readonly #handleParametersTouched = (): void => this.#markTouched('parameters');
    readonly #handleSchedulePreview = (): void => {
        this.#fieldState?.sync();
        this.#save?.notifyChanged();
    };

    constructor(dependencies: AutomationEditorSaveControllerDependencies) {
        this.#dependencies = dependencies;
    }

    dispose(): void {
        this.#save?.dispose();
        this.#save = null;
        this.#childLease?.controller.abort();
        this.#childLease?.release();
        this.#childLease = null;
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
        const saveButton = requireActionButton(modal, AUTOMATION_ACTION_SAVE_AUTOMATION);
        const form = this.#dependencies.modal.getForm();
        this.#fieldState = new AutomationConfigurationFieldStateController({
            modal,
            fieldErrors: form.getFieldErrorTargets(),
            validationSummary: form.getValidationSummary(),
            listTurnTextareas: () => form.listTurnTextareas(),
            readMcpConfig: () => form.readDraft().modelSettings.mcp,
            validate: () => form.validate()
        });
        this.#trackingAbort = new AbortController();
        this.#bindDirtyTracking(modal, this.#trackingAbort.signal);
        this.#attachSaveController(modal, saveButton);
    }

    notifyChanged(): void {
        this.#fieldState?.sync();
        this.#save?.notifyChanged();
    }

    resetPresentationBaseline(): void {
        this.#fieldState?.resetBaseline();
        this.#save?.notifyChanged();
    }

    async runChildModal(operation: (signal: AbortSignal, isCurrent: () => boolean) => Promise<boolean>): Promise<boolean> {
        if (!this.#save || this.#save.isSaving()) return false;
        const release = this.#childAdmission.acquire();
        if (release === null) return false;
        const lease = { token: this.#modalSessionToken.value, controller: new AbortController(), release };
        this.#childLease = lease;
        const isCurrent = (): boolean => this.#childLease === lease && this.#modalSessionToken.isActive(lease.token) && !lease.controller.signal.aborted;
        this.#save.notifyChanged();
        try {
            const applied = await raceWithAbortSignal(operation(lease.controller.signal, isCurrent), lease.controller.signal);
            if (applied && isCurrent()) this.notifyChanged();
            return applied && isCurrent();
        } catch (error) {
            const runtimeError = ensureError(error);
            if (isCurrent() && !isAbortError(runtimeError)) {
                errorHandler.warn('AutomationEditorSaveController', 'Automation child operation failed', runtimeError);
                this.#dependencies.showNotification(i18n.t('automation.modal.prerequisites.childFailed'), 'error');
            }
            return false;
        } finally {
            lease.release();
            if (this.#childLease === lease) {
                this.#childLease = null;
                this.#save?.notifyChanged();
            }
        }
    }

    async requestSave(): Promise<void> {
        if (!this.#save || this.#childLease !== null) {
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
        modal.addEventListener(AUTOMATION_CONFIGURATION_SCHEDULE_PREVIEW_EVENT, this.#handleSchedulePreview, { signal });
    }

    #markTouched(key: string): void {
        this.#fieldState?.markTouched(key);
        this.#fieldState?.sync();
    }

    #attachSaveController(modal: HTMLElement, saveButton: HTMLButtonElement): void {
        const sessionToken = this.#modalSessionToken.value;
        const save = createSaveController({
            headerContextId: 'automation:configuration-modal',
            headerPriority: SAVE_HEADER_PRIORITY_MODAL,
            requestContextLabel: 'Automation editor save',
            units: [
                {
                    id: 'automation:configuration',
                    hasChanges: () => this.#hasChanges(),
                    isValid: () => this.#childLease === null && this.#dependencies.modal.isEditable(),
                    save: async () => await this.#performSave()
                }
            ]
        });
        this.#save = save;
        save.attach({
            resolveSaveButtons: () => [saveButton],
            onBusyChange: (busy) => {
                if (this.#modalSessionToken.isActive(sessionToken)) this.#dependencies.modal.setFrozen('saving', busy);
            },
            autoNotifyRoot: modal,
            additionalDirtyEventNames: [AUTOMATION_CONFIGURATION_TURNS_UPDATED_EVENT, AUTOMATION_CONFIGURATION_WORKSPACE_UPDATED_EVENT, AUTOMATION_CONFIGURATION_PARAMETERS_UPDATED_EVENT]
        });
        this.#removeCloseGuard = attachBeforeCloseConfirmationGuard({
            modal,
            presenter: this.#dependencies.modalPresenter,
            modalId: modal.id,
            shouldConfirmClose: () => save.isSaving() || save.hasChanges(),
            confirmClose: async () => await this.#confirmDiscard(save)
        });
    }

    #hasChanges(): boolean {
        return this.#dependencies.modal.hasChanges();
    }

    async #confirmDiscard(save: SaveController): Promise<boolean> {
        if (save.isSaving()) {
            this.#dependencies.showNotification(i18n.t('common.processing'), 'info');
            return false;
        }
        return await showUnsavedChangesConfirmation();
    }

    async #performSave(): Promise<SaveUnitResult> {
        const fieldState = this.#fieldState;
        if (!fieldState) {
            return { type: 'stop' };
        }
        const validation = fieldState.sync();
        if (validation.validDraft === null) {
            fieldState.revealAllIssues(validation);
            return { type: 'stop' };
        }
        const submission = this.#dependencies.modal.readSubmission(validation.validDraft);
        if (!submission || (submission.type === 'update' && Object.keys(submission.payload).length === 0)) {
            return { type: 'stop' };
        }
        const sessionToken = this.#modalSessionToken.value;
        const outcome = await submitAutomationEditorSubmission(this.#dependencies.dataService, submission);
        if (outcome.type === 'saved') {
            await this.#settleAcceptedSave(outcome.automation, outcome.operation, sessionToken);
            return;
        }
        this.#reportRejectedSave(outcome, sessionToken);
        return { type: 'stop' };
    }

    #reportRejectedSave(outcome: Exclude<AutomationEditorSaveOutcome, { type: 'saved' }>, sessionToken: number): void {
        if (!this.#modalSessionToken.isActive(sessionToken)) return;
        if (outcome.type === 'conflict') {
            this.#dependencies.modal.showConflict(outcome.latest);
            this.#save?.notifyChanged();
            this.#dependencies.showNotification(i18n.t('automation.notifications.conflict'), 'warning');
            return;
        }
        if (outcome.type === 'missing') {
            this.#dependencies.modal.setPrerequisitesState({ type: 'failed', message: i18n.t('automation.notifications.missingOnSave'), retryable: false });
            this.#dependencies.showNotification(i18n.t('automation.notifications.missingOnSave'), 'error');
            return;
        }
        notifyAutomationEditorSaveFailure(outcome.error, this.#dependencies.showNotification);
        errorHandler.error('AutomationEditorSaveController', 'Failed to save automation', outcome.error);
    }

    async #settleAcceptedSave(automation: AutomationDefinitionResponse, operation: 'create' | 'update', sessionToken: number): Promise<void> {
        if (this.#modalSessionToken.isActive(sessionToken)) {
            this.#dependencies.modal.close();
        }
        this.#dependencies.showNotification(operation === 'create' ? i18n.t('automation.notifications.created') : i18n.t('automation.notifications.updated'), 'success');
        try {
            saveAutomationCreateDefaults(this.#dependencies.storage, automation);
        } catch (error) {
            errorHandler.warn('AutomationEditorSaveController', 'Saved automation, but failed to remember create defaults', ensureError(error));
            this.#dependencies.showNotification(i18n.t('automation.notifications.defaultsNotRemembered'), 'warning');
        }
        if (!this.#dependencies.isPageDisposed()) await refreshAfterAutomationChange(this.#dependencies, 'AutomationEditorSaveController');
    }
}

export { AutomationEditorSaveController };
