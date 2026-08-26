/* SoAI - Automation page child controllers [frontend/assets/ts/pages/automation/controllers/automationPageChildControllers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import { requireSyntaxHighlighter } from '@core/syntaxhighlighter/public.ts';
import { AutomationCalendarSettingsController } from '@pages/automation/controllers/AutomationCalendarSettingsController.ts';
import { AutomationEditorController } from '@pages/automation/controllers/AutomationEditorController.ts';
import { AutomationOccurrenceModalController } from '@pages/automation/controllers/AutomationOccurrenceModalController.ts';
import type { AutomationDataService } from '@features/automation/public.ts';
import type { AutomationCalendarSettings } from '@pages/automation/types.ts';

type AutomationPageChildControllersInitializeDependencies = {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modalPresenter: ModalPresenterApi;
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

type AutomationPageChildControllers = {
    editor: AutomationEditorController;
    occurrenceModal: AutomationOccurrenceModalController;
    calendarSettings: AutomationCalendarSettingsController;
};

const initializeAutomationPageChildControllers = async (dependencies: AutomationPageChildControllersInitializeDependencies): Promise<AutomationPageChildControllers> => {
    const editor = new AutomationEditorController({
        requireHTMLElement: dependencies.requireHTMLElement,
        modalPresenter: dependencies.modalPresenter,
        dataService: dependencies.dataService,
        storage: dependencies.storage,
        getIconSync: dependencies.getIconSync,
        getSelectedDateUtcMs: () => dependencies.getSelectedDateUtcMs(),
        refreshData: () => dependencies.refreshData(),
        showNotification: (message, type) => dependencies.showNotification(message, type)
    });
    const [availableModels, mcpCatalog] = await Promise.all([dependencies.dataService.listAvailableModels(), dependencies.dataService.getMcpCatalog()]);
    editor.setAvailableModels(availableModels);
    editor.setMcpCatalog(mcpCatalog);

    const occurrenceModal = new AutomationOccurrenceModalController({
        requireHTMLElement: dependencies.requireHTMLElement,
        modalPresenter: dependencies.modalPresenter,
        syntaxHighlighter: requireSyntaxHighlighter()
    });

    const calendarSettings = new AutomationCalendarSettingsController({
        requireHTMLElement: dependencies.requireHTMLElement,
        modalPresenter: dependencies.modalPresenter,
        getSettings: () => dependencies.getCalendarSettings(),
        setSettings: (settings) => dependencies.setCalendarSettings(settings),
        persistPreferences: () => dependencies.persistPreferences(),
        refreshData: () => dependencies.refreshData(),
        showNotification: (message, type) => dependencies.showNotification(message, type)
    });

    return { editor, occurrenceModal, calendarSettings };
};

export { initializeAutomationPageChildControllers };
export type { AutomationPageChildControllers };
