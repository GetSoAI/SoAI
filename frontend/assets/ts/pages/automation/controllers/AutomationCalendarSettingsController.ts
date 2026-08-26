/* SoAI - Automation page calendar settings controller [frontend/assets/ts/pages/automation/controllers/AutomationCalendarSettingsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { attachBeforeCloseConfirmationGuard } from '@core/modals/closeGuard.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { showUnsavedChangesConfirmation } from '@core/modals/unsavedChangesConfirmation.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL, type SaveController } from '@core/save/public.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import { AUTOMATION_ACTION_SAVE_CALENDAR_SETTINGS } from '@features/automation/public.ts';
import { AutomationCalendarSettingsFieldStateController } from '@pages/automation/controllers/configurationmodal/AutomationCalendarSettingsFieldStateController.ts';
import { AutomationCalendarSettingsModalController } from '@pages/automation/controllers/AutomationCalendarSettingsModalController.ts';
import { requireActionButton } from '@pages/automation/dom.ts';
import type { AutomationCalendarSettings } from '@pages/automation/types.ts';

interface CalendarSettingsControllerDependencies {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modalPresenter: ModalPresenterApi;
    getSettings: () => AutomationCalendarSettings;
    setSettings: (settings: AutomationCalendarSettings) => void;
    persistPreferences: () => void;
    refreshData: () => Promise<void>;
    showNotification: (message: string, type?: NotificationType, duration?: number) => void;
}

class AutomationCalendarSettingsController {
    readonly #dependencies: CalendarSettingsControllerDependencies;
    readonly #modal: AutomationCalendarSettingsModalController;
    readonly #modalSessionToken = new SequenceToken();
    #save: SaveController | null = null;
    #baselineSnapshotKey: string | null = null;
    #fieldState: AutomationCalendarSettingsFieldStateController | null = null;
    #trackingAbort: AbortController | null = null;
    #removeCloseGuard: (() => void) | null = null;

    constructor(dependencies: CalendarSettingsControllerDependencies) {
        this.#dependencies = dependencies;
        this.#modal = new AutomationCalendarSettingsModalController({
            requireHTMLElement: dependencies.requireHTMLElement,
            modalPresenter: dependencies.modalPresenter
        });
    }

    #disposeModalTracking(): void {
        this.#save?.dispose();
        this.#save = null;
        this.#baselineSnapshotKey = null;
        this.#fieldState?.clear();
        this.#fieldState = null;
        this.#trackingAbort?.abort();
        this.#trackingAbort = null;
        this.#removeCloseGuard?.();
        this.#removeCloseGuard = null;
        this.#modalSessionToken.invalidate();
    }

    connect(signal: AbortSignal): void {
        this.#modal.connect(signal);
    }

    onCalendarSettingsModalOpen(modal: Element): void {
        if (!(modal instanceof HTMLElement)) {
            throw new TypeError('Automation calendar settings modal root must be an HTMLElement');
        }
        this.#disposeModalTracking();
        this.#modalSessionToken.next();
        const saveButton = requireActionButton(modal, AUTOMATION_ACTION_SAVE_CALENDAR_SETTINGS);
        this.#baselineSnapshotKey = this.#modal.getSnapshotKey();
        this.#fieldState = new AutomationCalendarSettingsFieldStateController(modal);
        this.#trackingAbort = new AbortController();
        const { signal } = this.#trackingAbort;
        const syncFieldState = (): void => this.#fieldState?.sync();
        modal.addEventListener('input', syncFieldState, { signal, capture: true });
        modal.addEventListener('change', syncFieldState, { signal, capture: true });
        const save = createSaveController({
            headerContextId: 'automation:calendar-settings-modal',
            headerPriority: SAVE_HEADER_PRIORITY_MODAL,
            requestContextLabel: 'Automation calendar settings save',
            units: [
                {
                    id: 'automation:calendar-settings',
                    hasChanges: () => {
                        if (!this.#modal.isOpen() || this.#baselineSnapshotKey === null) {
                            return false;
                        }
                        return this.#modal.getSnapshotKey() !== this.#baselineSnapshotKey;
                    },
                    isValid: () => (this.#modal.isOpen() ? this.#modal.isValid() : false),
                    save: async () => this.#performSaveCalendarSettings()
                }
            ]
        });
        this.#save = save;
        setAriaBusy(modal, false);
        save.attach({
            resolveSaveButtons: () => [saveButton],
            busyRoots: [modal],
            autoNotifyRoot: modal
        });
        this.#removeCloseGuard = attachBeforeCloseConfirmationGuard({
            modal,
            presenter: this.#dependencies.modalPresenter,
            modalId: modal.id,
            shouldConfirmClose: () => save.isSaving() || save.hasChanges(),
            confirmClose: async () => await this.#confirmDiscard(save)
        });
    }

    onCalendarSettingsModalClose(): void {
        this.#disposeModalTracking();
    }

    destroy(): void {
        this.#disposeModalTracking();
    }

    open(): void {
        this.#modal.open(this.#dependencies.getSettings());
    }

    async save(): Promise<void> {
        if (!this.#save) {
            return;
        }
        await this.#save.requestSave();
    }

    async #confirmDiscard(save: SaveController): Promise<boolean> {
        if (save.isSaving()) {
            this.#dependencies.showNotification(i18n.t('common.processing'), 'info');
            return false;
        }
        return await showUnsavedChangesConfirmation();
    }

    async #performSaveCalendarSettings(): Promise<void> {
        const next = this.#modal.readAndValidate();
        if (!next) {
            return;
        }
        const modalSessionToken = this.#modalSessionToken.value;
        try {
            this.#dependencies.setSettings(next);
            this.#dependencies.persistPreferences();
        } catch (error) {
            const runtimeError = ensureError(error);
            showOperationFailureNotification({
                error: runtimeError,
                operation: i18n.t('common.save'),
                showNotification: (message, level): void => this.#dependencies.showNotification(message, level)
            });
            errorHandler.error('AutomationCalendarSettingsController', 'Failed to save calendar settings', runtimeError);
            return;
        }

        if (this.#modalSessionToken.isActive(modalSessionToken)) {
            this.#modal.close();
        }

        try {
            await this.#dependencies.refreshData();
        } catch (error) {
            const refreshError = ensureError(error);
            showOperationFailureNotification({
                error: refreshError,
                operation: i18n.t('common.refresh'),
                showNotification: (message, level): void => this.#dependencies.showNotification(message, level)
            });
            errorHandler.error('AutomationCalendarSettingsController', 'Refresh failed after saving calendar settings', refreshError);
            return;
        }

        this.#dependencies.showNotification(i18n.t('automation.notifications.calendarSettingsSaved'), 'success');
    }
}

export { AutomationCalendarSettingsController };
