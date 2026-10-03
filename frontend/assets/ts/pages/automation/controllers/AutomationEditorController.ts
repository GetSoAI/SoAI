/* SoAI - Automation page editor controller [frontend/assets/ts/pages/automation/controllers/AutomationEditorController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { raceWithAbortSignal } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import { toStartLocal } from '@core/time/localCalendar.ts';
import { AutomationConfigurationModalController } from '@pages/automation/controllers/AutomationConfigurationModalController.ts';
import { resolveAutomationCreateStartLocal } from '@pages/automation/controllers/AutomationCreateStartDomain.ts';
import { AutomationEditorSaveController } from '@pages/automation/controllers/AutomationEditorSaveController.ts';
import { AUTOMATION_TIMEZONE_AUTO } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFormUi.ts';
import { resolveAutomationCreateDefaults } from '@pages/automation/state/AutomationCreateDefaultsManager.ts';
import type { AutomationDataService, AutomationDefinitionResponse, AutomationMcpCatalogResponse } from '@features/automation/public.ts';
import type { AutomationCalendarSettings } from '@pages/automation/types.ts';

interface AutomationEditorControllerDependencies {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modalPresenter: ModalPresenterApi;
    dataService: AutomationDataService;
    storage: StorageService;
    getIconSync: (icon: IconName, options?: IconOptions) => TrustedHtml;
    getSelectedDateUtcMs: () => number;
    getCalendarSettings: () => AutomationCalendarSettings;
    refreshData: () => Promise<void>;
    showNotification: (message: string, type?: NotificationType, duration?: number) => void;
}

type AutomationEditorOpenRequest = { mode: 'create'; startLocal: string } | { mode: 'edit' | 'preview'; automationId: string; onReady: (() => void) | null };

const settledValue = <T>(result: PromiseSettledResult<T>): T | null => (result.status === 'fulfilled' ? result.value : null);

class AutomationEditorController {
    readonly #dependencies: AutomationEditorControllerDependencies;
    readonly #modal: AutomationConfigurationModalController;
    readonly #saveSession: AutomationEditorSaveController;
    readonly #loadToken = new SequenceToken();
    #request: AutomationEditorOpenRequest | null = null;
    #currentWorkspacePath: string | null = null;
    #destroyed = false;
    #loadAbort: AbortController | null = null;

    constructor(dependencies: AutomationEditorControllerDependencies) {
        this.#dependencies = dependencies;
        this.#modal = new AutomationConfigurationModalController({
            requireHTMLElement: dependencies.requireHTMLElement,
            modalPresenter: dependencies.modalPresenter,
            getIconSync: dependencies.getIconSync,
            previewSchedule: (input, signal) => dependencies.dataService.previewSchedule(input, signal),
            getCalendarSettings: dependencies.getCalendarSettings
        });
        this.#saveSession = new AutomationEditorSaveController({
            modalPresenter: dependencies.modalPresenter,
            modal: this.#modal,
            dataService: dependencies.dataService,
            storage: dependencies.storage,
            refreshData: dependencies.refreshData,
            isPageDisposed: () => this.#destroyed,
            showNotification: dependencies.showNotification
        });
    }

    onConfigurationModalOpen(modal: Element): void {
        this.#saveSession.begin(modal);
    }

    onConfigurationModalClose(): void {
        this.#loadToken.invalidate();
        this.#loadAbort?.abort();
        this.#loadAbort = null;
        this.#request = null;
        this.#saveSession.dispose();
        this.#modal.endSession();
    }

    destroy(): void {
        this.#destroyed = true;
        this.#loadToken.invalidate();
        this.#loadAbort?.abort();
        this.#loadAbort = null;
        this.#request = null;
        if (this.#modal.isOpen()) {
            this.#modal.dismiss();
        }
        this.#saveSession.dispose();
        this.#modal.destroy();
    }

    async openCreateForSelectedDate(): Promise<void> {
        await this.#open({ mode: 'create', startLocal: resolveAutomationCreateStartLocal(this.#dependencies.getSelectedDateUtcMs(), Date.now()) });
    }

    async openCreateAtUtcMs(scheduledAtUtcMs: number): Promise<void> {
        await this.#open({ mode: 'create', startLocal: toStartLocal(new Date(scheduledAtUtcMs)) });
    }

    async openEdit(automationId: string, onReady: (() => void) | null = null): Promise<void> {
        await this.#open({ mode: 'edit', automationId, onReady });
    }

    async openPreview(automationId: string, onReady: (() => void) | null = null): Promise<void> {
        await this.#open({ mode: 'preview', automationId, onReady });
    }

    async retryPrerequisites(): Promise<void> {
        if (this.#request === null || !this.#modal.isOpen()) {
            return;
        }
        if (this.#modal.arePrerequisitesReady()) {
            await this.#retryToolCatalog();
            return;
        }
        await this.#loadPrerequisites(this.#request);
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

    keepChangesAfterConflict(): void {
        if (this.#modal.keepChangesAfterConflict(() => this.#saveSession.resetPresentationBaseline())) {
            this.#saveSession.notifyChanged();
        }
    }

    loadLatestAfterConflict(): void {
        const latest = this.#modal.takePendingConflict();
        if (latest === null || this.#currentWorkspacePath === null) {
            return;
        }
        this.#modal.applyDefinition(latest, this.#currentWorkspacePath);
        this.#saveSession.resetPresentationBaseline();
    }

    async openWorkspaceModal(): Promise<void> {
        await this.#saveSession.runChildModal(async (signal, isCurrent) => {
            const workspaceAccess = await raceWithAbortSignal(this.#dependencies.dataService.getWorkspaceAccess(signal), signal);
            if (!isCurrent()) return false;
            return await this.#modal.openWorkspaceModal(workspaceAccess.browserApi, signal);
        });
    }

    async openParametersModal(): Promise<void> {
        await this.#saveSession.runChildModal(async (signal, isCurrent) => {
            if (!isCurrent()) return false;
            return await this.#modal.openParametersModal(signal);
        });
    }

    async saveFromModal(): Promise<void> {
        await this.#saveSession.requestSave();
    }

    async #open(request: AutomationEditorOpenRequest): Promise<void> {
        if (this.#destroyed) {
            return;
        }
        if (this.#modal.isOpen()) this.#modal.dismiss();
        this.#request = request;
        this.#modal.beginOpen(request.mode);
        await this.#loadPrerequisites(request);
    }

    async #loadPrerequisites(request: AutomationEditorOpenRequest): Promise<void> {
        const token = this.#loadToken.next();
        this.#loadAbort?.abort();
        const controller = new AbortController();
        this.#loadAbort = controller;
        const signal = controller.signal;
        this.#modal.setPrerequisitesState({ type: 'loading' });
        const dataService = this.#dependencies.dataService;
        const results = await raceWithAbortSignal(Promise.allSettled([dataService.getWorkspaceAccess(signal), dataService.listAvailableModels(signal), dataService.getMcpCatalog({ signal }), request.mode === 'create' ? Promise.resolve(null) : dataService.getAutomation(request.automationId, signal)]), signal).catch((error) => {
            const runtimeError = ensureError(error);
            if (!signal.aborted) throw runtimeError;
            errorHandler.debug('AutomationEditorController', 'Editor prerequisite load cancelled', runtimeError);
            return null;
        });
        if (results === null) return;
        const [workspaceResult, modelsResult, catalogResult, definitionResult] = results;
        if (this.#destroyed || !this.#loadToken.isActive(token) || this.#request !== request) {
            return;
        }
        const workspace = settledValue(workspaceResult);
        const models = settledValue(modelsResult);
        const catalog = settledValue(catalogResult);
        const definition = settledValue(definitionResult);
        const failures = [workspaceResult, modelsResult, catalogResult, definitionResult].flatMap((result) => (result.status === 'rejected' ? [ensureError(result.reason)] : []));
        failures.forEach((error) => errorHandler.warn('AutomationEditorController', 'Failed to load automation editor prerequisites', error));
        const definitionError = definitionResult.status === 'rejected' ? ensureError(definitionResult.reason) : null;
        if (definitionError instanceof APIError && definitionError.status === 404) {
            this.#modal.setPrerequisitesState({ type: 'failed', message: i18n.t('automation.modal.prerequisites.missing'), retryable: false });
            return;
        }
        if (!workspace || !models || (request.mode === 'create' ? !catalog : !definition)) {
            this.#modal.setPrerequisitesState({ type: 'failed', message: i18n.t('automation.modal.prerequisites.failed'), retryable: true });
            return;
        }
        try {
            this.#currentWorkspacePath = workspace.currentWorkspacePath;
            this.#modal.setAvailableModels(models);
            if (catalog) this.#modal.setMcpCatalog(catalog);
            this.#applyRequest(request, catalog, definition);
            this.#modal.setToolsUnavailable(catalog === null);
            this.#modal.setPrerequisitesState({ type: 'ready' });
            this.#saveSession.resetPresentationBaseline();
        } catch (error) {
            errorHandler.error('AutomationEditorController', 'Automation form initialization failed', ensureError(error));
            this.#modal.setPrerequisitesState({ type: 'failed', message: i18n.t('automation.modal.prerequisites.failed'), retryable: true });
            return;
        }
        if (!this.#destroyed && this.#loadToken.isActive(token) && request.mode !== 'create') request.onReady?.();
    }

    #applyRequest(request: AutomationEditorOpenRequest, catalog: AutomationMcpCatalogResponse | null, definition: AutomationDefinitionResponse | null): void {
        const currentWorkspacePath = this.#currentWorkspacePath ?? '';
        if (request.mode === 'create') {
            this.#modal.applyCreate({ startLocal: request.startLocal, timezone: AUTOMATION_TIMEZONE_AUTO, createDefaults: resolveAutomationCreateDefaults(this.#dependencies.storage, catalog), currentWorkspacePath });
            return;
        }
        if (definition === null) {
            throw new Error('Automation editor requires a loaded definition');
        }
        this.#modal.applyDefinition(definition, currentWorkspacePath);
    }

    async #retryToolCatalog(): Promise<void> {
        const request = this.#request;
        const token = this.#loadToken.next();
        try {
            const catalog = await this.#dependencies.dataService.getMcpCatalog({ signal: this.#loadAbort?.signal, refresh: true });
            if (this.#destroyed || !this.#loadToken.isActive(token) || this.#request !== request) {
                return;
            }
            this.#modal.setMcpCatalog(catalog);
            this.#modal.setToolsUnavailable(false);
            this.#saveSession.notifyChanged();
        } catch (error) {
            if (this.#destroyed || !this.#loadToken.isActive(token) || this.#request !== request) return;
            errorHandler.warn('AutomationEditorController', 'Failed to reload automation tool catalog', ensureError(error));
            this.#dependencies.showNotification(i18n.t('automation.modal.prerequisites.toolsUnavailable'), 'error');
        }
    }
}

export { AutomationEditorController };
