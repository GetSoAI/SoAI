/* SoAI - Automation page editor controller [frontend/assets/ts/pages/automation/controllers/AutomationEditorController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import { toStartLocal } from '@core/time/localCalendar.ts';
import { AutomationConfigurationModalController } from '@pages/automation/controllers/AutomationConfigurationModalController.ts';
import { AutomationEditorSaveController } from '@pages/automation/controllers/AutomationEditorSaveController.ts';
import { resolveAutomationCreateDefaults, type AutomationCreateDefaults } from '@pages/automation/state/AutomationCreateDefaultsManager.ts';
import type { AutomationDataService, AutomationDefinition, AutomationMcpCatalog, AutomationModelOption, AutomationWorkspaceAccess } from '@features/automation/public.ts';

interface AutomationEditorControllerDependencies {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modalPresenter: ModalPresenterApi;
    dataService: AutomationDataService;
    storage: StorageService;
    getIconSync: (icon: IconName, options?: IconOptions) => TrustedHtml;
    getSelectedDateUtcMs: () => number;
    refreshData: () => Promise<void>;
    showNotification: (message: string, type?: NotificationType, duration?: number) => void;
}

type AutomationModalOpenData = {
    workspaceAccess: AutomationWorkspaceAccess;
    availableModels: readonly AutomationModelOption[];
};

class AutomationEditorController {
    readonly #dependencies: AutomationEditorControllerDependencies;
    readonly #modal: AutomationConfigurationModalController;
    readonly #saveSession: AutomationEditorSaveController;
    readonly #modalOpenToken = new SequenceToken();
    #mcpCatalog: AutomationMcpCatalog | null = null;

    constructor(dependencies: AutomationEditorControllerDependencies) {
        this.#dependencies = dependencies;
        this.#modal = new AutomationConfigurationModalController({
            requireHTMLElement: dependencies.requireHTMLElement,
            modalPresenter: dependencies.modalPresenter,
            getIconSync: dependencies.getIconSync
        });
        this.#saveSession = new AutomationEditorSaveController({
            requireHTMLElement: dependencies.requireHTMLElement,
            modalPresenter: dependencies.modalPresenter,
            modal: this.#modal,
            dataService: dependencies.dataService,
            storage: dependencies.storage,
            refreshData: dependencies.refreshData,
            showNotification: dependencies.showNotification
        });
    }

    onConfigurationModalOpen(modal: Element): void {
        this.#saveSession.begin(modal);
    }

    onConfigurationModalClose(): void {
        this.#saveSession.dispose();
    }

    destroy(): void {
        this.#modal.destroy();
        this.#saveSession.dispose();
    }

    setAvailableModels(models: readonly AutomationModelOption[]): void {
        this.#modal.setAvailableModels(models);
        this.#saveSession.resetBaselineToCurrentIfUntouched();
    }

    setMcpCatalog(catalog: AutomationMcpCatalog): void {
        this.#mcpCatalog = catalog;
        this.#modal.setMcpCatalog(catalog);
        this.#saveSession.resetBaselineToCurrentIfUntouched();
    }

    async openCreateForSelectedDate(): Promise<void> {
        const selected = new Date(this.#dependencies.getSelectedDateUtcMs());
        selected.setHours(9, 0, 0, 0);
        await this.#openCreateForDate(selected);
    }

    async openCreateAtUtcMs(scheduledAtUtcMs: number): Promise<void> {
        await this.#openCreateForDate(new Date(scheduledAtUtcMs));
    }

    async openEdit(automation: AutomationDefinition): Promise<void> {
        const token = this.#modalOpenToken.next();
        const modalData = await this.#loadModalOpenData();
        if (!this.#modalOpenToken.isActive(token)) {
            return;
        }
        this.setAvailableModels(modalData.availableModels);
        this.#modal.openEdit(automation, modalData.workspaceAccess.currentWorkspacePath);
    }

    async openPreview(automation: AutomationDefinition): Promise<void> {
        const token = this.#modalOpenToken.next();
        const modalData = await this.#loadModalOpenData();
        if (!this.#modalOpenToken.isActive(token)) {
            return;
        }
        this.setAvailableModels(modalData.availableModels);
        this.#modal.openPreview(automation, modalData.workspaceAccess.currentWorkspacePath);
    }

    enterEditMode(): void {
        this.#modal.enterEditMode();
        this.#saveSession.notifyChanged();
    }

    addTurn(): void {
        this.#modal.addTurn();
    }

    removeTurn(turnIndex: string | null): void {
        this.#modal.removeTurn(turnIndex);
    }

    async openWorkspaceModal(): Promise<void> {
        const applied = await this.#saveSession.runChildModal(async () => {
            const workspaceAccess = await this.#dependencies.dataService.getWorkspaceAccess();
            return await this.#modal.openWorkspaceModal(workspaceAccess.browserApi);
        });
        if (applied) {
            this.#saveSession.notifyChanged();
        }
    }

    async openParametersModal(): Promise<void> {
        const applied = await this.#saveSession.runChildModal(async () => await this.#modal.openParametersModal());
        if (applied) {
            this.#saveSession.notifyChanged();
        }
    }

    async saveFromModal(): Promise<void> {
        await this.#saveSession.requestSave();
    }

    async #openCreateForDate(date: Date): Promise<void> {
        const token = this.#modalOpenToken.next();
        const modalData = await this.#loadModalOpenData();
        if (!this.#modalOpenToken.isActive(token)) {
            return;
        }
        this.setAvailableModels(modalData.availableModels);
        this.#modal.openCreate({
            startLocal: toStartLocal(date),
            timezone: 'auto',
            createDefaults: this.#resolveCreateDefaults(),
            currentWorkspacePath: modalData.workspaceAccess.currentWorkspacePath
        });
    }

    async #loadModalOpenData(): Promise<AutomationModalOpenData> {
        const [workspaceAccess, availableModels] = await Promise.all([this.#dependencies.dataService.getWorkspaceAccess(), this.#dependencies.dataService.listAvailableModels()]);
        return { workspaceAccess, availableModels };
    }

    #resolveCreateDefaults(): AutomationCreateDefaults {
        return resolveAutomationCreateDefaults(this.#dependencies.storage, this.#mcpCatalog);
    }
}

export { AutomationEditorController };
