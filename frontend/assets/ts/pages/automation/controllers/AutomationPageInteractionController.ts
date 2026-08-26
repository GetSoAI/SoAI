/* SoAI - Automation page interaction controller [frontend/assets/ts/pages/automation/controllers/AutomationPageInteractionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import type { AutomationCalendarSettingsController } from '@pages/automation/controllers/AutomationCalendarSettingsController.ts';
import type { AutomationEditorController } from '@pages/automation/controllers/AutomationEditorController.ts';
import type { AutomationOccurrenceModalController } from '@pages/automation/controllers/AutomationOccurrenceModalController.ts';
import { AutomationPageChildControllerHost } from '@pages/automation/controllers/AutomationPageChildControllerHost.ts';
import { AutomationPageUiConnectionsController } from '@pages/automation/controllers/AutomationPageUiConnectionsController.ts';
import { persistAutomationPagePreferences } from '@pages/automation/state/preferences.ts';
import type { AutomationDataService } from '@features/automation/public.ts';
import type { AutomationPageState, AutomationUiRefs } from '@pages/automation/types.ts';

interface AutomationPageInteractionInitializationDependencies {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modalPresenter: ModalPresenterApi;
    api: ApiClient;
    dataService: AutomationDataService;
    getIconSync: (icon: IconName, options?: IconOptions) => TrustedHtml;
    getState: () => AutomationPageState;
    setState: (next: AutomationPageState) => void;
    refreshData: () => Promise<void>;
    showNotification: (message: string, type?: NotificationType) => void;
    storage: StorageService;
    isPreferencesCorrupt: () => boolean;
}

interface AutomationPageInteractionDependencies {
    initialization: AutomationPageInteractionInitializationDependencies;
    ui: AutomationUiRefs;
    applySplit: (value: number) => void;
    getHourHeightPx: () => number;
    requestAnimationFrame: (callback: () => void) => number;
    setTimeout: (callback: () => void, delay: number) => number | null;
    clearTimer: (timerId: number | null | undefined) => void;
    setMonthMaxChipsPerDay: (value: number) => void;
    queueRender: () => void;
    run: (operation: string, task: () => Promise<void> | void) => void;
    realtimeConnect: (signal: AbortSignal) => void;
    shiftVisiblePeriod: (offset: number) => Promise<void>;
}

class AutomationPageInteractionController {
    readonly #dependencies: AutomationPageInteractionDependencies;
    readonly #childControllers = new AutomationPageChildControllerHost();
    #connections: AutomationPageUiConnectionsController | null = null;
    #connectionAbortController: AbortController | null = null;
    #interactiveReady = false;
    #connected = false;
    readonly #onAbort = (): void => {
        this.disconnect();
    };

    constructor(dependencies: AutomationPageInteractionDependencies) {
        this.#dependencies = dependencies;
    }

    async initialize(): Promise<void> {
        if (this.#interactiveReady) {
            return;
        }
        await this.#childControllers.initialize({
            requireHTMLElement: this.#dependencies.initialization.requireHTMLElement,
            modalPresenter: this.#dependencies.initialization.modalPresenter,
            api: this.#dependencies.initialization.api,
            dataService: this.#dependencies.initialization.dataService,
            storage: this.#dependencies.initialization.storage,
            getIconSync: this.#dependencies.initialization.getIconSync,
            getSelectedDateUtcMs: () => this.#dependencies.initialization.getState().selectedDateUtcMs,
            refreshData: this.#dependencies.initialization.refreshData,
            showNotification: this.#dependencies.initialization.showNotification,
            getCalendarSettings: () => this.#dependencies.initialization.getState().calendarSettings,
            setCalendarSettings: (settings) => {
                this.#dependencies.initialization.setState({ ...this.#dependencies.initialization.getState(), calendarSettings: settings });
            },
            persistPreferences: () => persistAutomationPagePreferences(this.#dependencies.initialization.storage, this.#dependencies.initialization.getState(), this.#dependencies.initialization.isPreferencesCorrupt())
        });
        this.#interactiveReady = true;
    }

    connect(signal: AbortSignal): void {
        if (signal.aborted || this.#connected) {
            return;
        }
        const editor = this.#childControllers.getEditor();
        if (!editor) {
            throw new Error('Automation editor is not initialized');
        }
        const connectionAbortController = new AbortController();
        const connectionSignal = connectionAbortController.signal;
        this.#connectionAbortController = connectionAbortController;
        try {
            this.#connections = new AutomationPageUiConnectionsController({
                ui: this.#dependencies.ui,
                getViewMode: () => this.#dependencies.initialization.getState().viewMode,
                getInitialSplitPercent: () => this.#dependencies.initialization.getState().splitLeftPercent,
                setSplitPercent: (value) => {
                    const state = this.#dependencies.initialization.getState();
                    this.#dependencies.initialization.setState({ ...state, splitLeftPercent: value });
                    this.#dependencies.applySplit(value);
                },
                commitSplitPercent: (value) => {
                    const state = this.#dependencies.initialization.getState();
                    this.#dependencies.initialization.setState({ ...state, splitLeftPercent: value });
                    this.#dependencies.applySplit(value);
                    persistAutomationPagePreferences(this.#dependencies.initialization.storage, this.#dependencies.initialization.getState(), this.#dependencies.initialization.isPreferencesCorrupt());
                },
                openCreateModalAt: (utcMs) => {
                    this.#dependencies.run('automation:openCreateModalAt', async () => {
                        await editor.openCreateAtUtcMs(utcMs);
                    });
                },
                hourHeightPx: this.#dependencies.getHourHeightPx(),
                requestAnimationFrame: this.#dependencies.requestAnimationFrame,
                setTimeout: this.#dependencies.setTimeout,
                clearTimer: this.#dependencies.clearTimer,
                setMonthMaxChipsPerDay: this.#dependencies.setMonthMaxChipsPerDay,
                queueRender: this.#dependencies.queueRender,
                shiftVisiblePeriod: this.#dependencies.shiftVisiblePeriod
            });
            this.#connections.connect(connectionSignal);
            this.#childControllers.connect(connectionSignal);
            this.#dependencies.realtimeConnect(connectionSignal);
            this.#connected = true;
            signal.addEventListener('abort', this.#onAbort, { once: true });
        } catch (error) {
            this.disconnect();
            throw error;
        }
    }

    disconnect(): void {
        this.#connectionAbortController?.abort();
        this.#connectionAbortController = null;
        this.#connections?.destroy();
        this.#connections = null;
        this.#connected = false;
    }

    destroy(): void {
        this.disconnect();
        this.#childControllers.destroy();
        this.#interactiveReady = false;
    }

    getConnections(): AutomationPageUiConnectionsController | null {
        return this.#connections;
    }

    cancelPendingScrollShift(): void {
        this.#connections?.cancelPendingScrollShift();
    }

    getEditor(): AutomationEditorController | null {
        return this.#childControllers.getEditor();
    }

    getCalendarSettingsController(): AutomationCalendarSettingsController | null {
        return this.#childControllers.getCalendarSettingsController();
    }

    getOccurrenceModal(): AutomationOccurrenceModalController | null {
        return this.#childControllers.getOccurrenceModal();
    }

    onConfigurationModalOpen(modal: Element): void {
        this.#childControllers.onConfigurationModalOpen(modal);
    }

    onConfigurationModalClose(): void {
        this.#childControllers.onConfigurationModalClose();
    }

    onCalendarSettingsModalOpen(modal: Element): void {
        this.#childControllers.onCalendarSettingsModalOpen(modal);
    }

    onCalendarSettingsModalClose(): void {
        this.#childControllers.onCalendarSettingsModalClose();
    }
}

export { AutomationPageInteractionController };
