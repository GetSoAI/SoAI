/* SoAI - Automation page child controller host [frontend/assets/ts/pages/automation/controllers/AutomationPageChildControllerHost.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import { AutomationCalendarSettingsController } from '@pages/automation/controllers/AutomationCalendarSettingsController.ts';
import { AutomationEditorController } from '@pages/automation/controllers/AutomationEditorController.ts';
import { AutomationOccurrenceModalController } from '@pages/automation/controllers/AutomationOccurrenceModalController.ts';
import { initializeAutomationPageChildControllers } from '@pages/automation/controllers/automationPageChildControllers.ts';
import type { AutomationDataService } from '@features/automation/public.ts';
import type { AutomationCalendarSettings } from '@pages/automation/types.ts';

type AutomationPageChildControllerHostInitializationDependencies = {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modalPresenter: ModalPresenterApi;
    api: ApiClient;
    dataService: AutomationDataService;
    storage: StorageService;
    getIconSync: (icon: IconName, options?: IconOptions) => TrustedHtml;
    getSelectedDateUtcMs: () => number;
    refreshData: () => Promise<void>;
    showNotification: (message: string, type?: NotificationType) => void;
    getCalendarSettings: () => AutomationCalendarSettings;
    setCalendarSettings: (settings: AutomationCalendarSettings) => void;
    persistPreferences: () => void;
};

class AutomationPageChildControllerHost {
    #editor: AutomationEditorController | null = null;
    #calendarSettings: AutomationCalendarSettingsController | null = null;
    #occurrenceModal: AutomationOccurrenceModalController | null = null;

    async initialize(dependencies: AutomationPageChildControllerHostInitializationDependencies): Promise<void> {
        const childControllers = await initializeAutomationPageChildControllers(dependencies);
        this.#editor = childControllers.editor;
        this.#occurrenceModal = childControllers.occurrenceModal;
        this.#calendarSettings = childControllers.calendarSettings;
    }

    connect(signal: AbortSignal): void {
        this.#calendarSettings?.connect(signal);
    }

    destroy(): void {
        this.#editor?.destroy();
        this.#editor = null;
        this.#calendarSettings?.destroy();
        this.#calendarSettings = null;
        this.#occurrenceModal = null;
    }

    getEditor(): AutomationEditorController | null {
        return this.#editor;
    }

    getCalendarSettingsController(): AutomationCalendarSettingsController | null {
        return this.#calendarSettings;
    }

    getOccurrenceModal(): AutomationOccurrenceModalController | null {
        return this.#occurrenceModal;
    }

    onConfigurationModalOpen(modal: Element): void {
        if (!this.#editor) {
            throw new Error('Automation editor is not initialized');
        }
        this.#editor.onConfigurationModalOpen(modal);
    }

    onConfigurationModalClose(): void {
        this.#editor?.onConfigurationModalClose();
    }

    onCalendarSettingsModalOpen(modal: Element): void {
        if (!this.#calendarSettings) {
            throw new Error('Automation calendar settings controller is not initialized');
        }
        this.#calendarSettings.onCalendarSettingsModalOpen(modal);
    }

    onCalendarSettingsModalClose(): void {
        this.#calendarSettings?.onCalendarSettingsModalClose();
    }
}

export { AutomationPageChildControllerHost };
