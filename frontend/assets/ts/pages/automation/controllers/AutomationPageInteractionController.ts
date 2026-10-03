/* SoAI - Automation page interaction controller [frontend/assets/ts/pages/automation/controllers/AutomationPageInteractionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { CleanupStack } from '@core/lifecycle/cleanupStack.ts';
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
import { AutomationPageUiConnectionsController } from '@pages/automation/controllers/AutomationPageUiConnectionsController.ts';
import { persistAutomationPagePreferences } from '@pages/automation/state/preferences.ts';
import type { AutomationDataService } from '@features/automation/public.ts';
import type { AutomationPageState, AutomationUiRefs } from '@pages/automation/types.ts';

interface AutomationPageInteractionInitializationDependencies {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modalPresenter: ModalPresenterApi;
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
    #editor: AutomationEditorController | null = null;
    #calendarSettings: AutomationCalendarSettingsController | null = null;
    #occurrenceModal: AutomationOccurrenceModalController | null = null;
    #childCleanup: CleanupStack | null = null;
    #connections: AutomationPageUiConnectionsController | null = null;
    #connectionAbortController: AbortController | null = null;
    #interactiveReady = false;
    #connected = false;
    readonly #onAbort = (): void => {
        this.disconnect();
    };
    readonly #onOccurrenceClosed = (zoneKey: string): void => {
        const initialization = this.#dependencies.initialization;
        const state = initialization.getState();
        if (state.selectedZoneKey !== zoneKey) return;
        initialization.setState({ ...state, selectedZoneKey: null });
        this.#dependencies.queueRender();
    };

    constructor(dependencies: AutomationPageInteractionDependencies) {
        this.#dependencies = dependencies;
    }

    initialize(): void {
        if (this.#interactiveReady) {
            return;
        }
        const initialization = this.#dependencies.initialization;
        const childCleanup = new CleanupStack({
            logError: (message, error) => errorHandler.error('AutomationPageInteractionController', message, error)
        });
        try {
            const editor = new AutomationEditorController({
                requireHTMLElement: initialization.requireHTMLElement,
                modalPresenter: initialization.modalPresenter,
                dataService: initialization.dataService,
                storage: initialization.storage,
                getIconSync: initialization.getIconSync,
                getSelectedDateUtcMs: () => initialization.getState().selectedDateUtcMs,
                getCalendarSettings: () => initialization.getState().calendarSettings,
                refreshData: initialization.refreshData,
                showNotification: initialization.showNotification
            });
            childCleanup.add(() => editor.destroy());
            const occurrenceModal = new AutomationOccurrenceModalController({
                requireHTMLElement: initialization.requireHTMLElement,
                modalPresenter: initialization.modalPresenter,
                syntaxHighlighter: requireSyntaxHighlighter(),
                dataService: initialization.dataService
            });
            childCleanup.add(() => occurrenceModal.destroy());
            const calendarSettings = new AutomationCalendarSettingsController({
                requireHTMLElement: initialization.requireHTMLElement,
                modalPresenter: initialization.modalPresenter,
                getSettings: () => initialization.getState().calendarSettings,
                saveSettings: (settings) => {
                    const nextState = { ...initialization.getState(), calendarSettings: settings };
                    persistAutomationPagePreferences(initialization.storage, nextState, initialization.isPreferencesCorrupt());
                    initialization.setState(nextState);
                    this.#dependencies.queueRender();
                },
                refreshData: initialization.refreshData,
                showNotification: initialization.showNotification
            });
            childCleanup.add(() => calendarSettings.destroy());
            this.#editor = editor;
            this.#occurrenceModal = occurrenceModal;
            this.#calendarSettings = calendarSettings;
            this.#childCleanup = childCleanup;
            this.#interactiveReady = true;
        } catch (error) {
            childCleanup.dispose();
            throw error;
        }
    }

    connect(signal: AbortSignal): void {
        if (signal.aborted || this.#connected) {
            return;
        }
        const editor = this.#editor;
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
                getTimeFormat: () => this.#dependencies.initialization.getState().calendarSettings.timeFormat,
                hourHeightPx: this.#dependencies.getHourHeightPx(),
                requestAnimationFrame: this.#dependencies.requestAnimationFrame,
                setTimeout: this.#dependencies.setTimeout,
                clearTimer: this.#dependencies.clearTimer,
                setMonthMaxChipsPerDay: this.#dependencies.setMonthMaxChipsPerDay,
                queueRender: this.#dependencies.queueRender,
                shiftVisiblePeriod: this.#dependencies.shiftVisiblePeriod
            });
            this.#connections.connect(connectionSignal);
            this.#calendarSettings?.connect(connectionSignal);
            this.#occurrenceModal?.connect(connectionSignal, this.#onOccurrenceClosed);
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
        this.#childCleanup?.dispose();
        this.#childCleanup = null;
        this.#editor = null;
        this.#calendarSettings = null;
        this.#occurrenceModal = null;
        this.#interactiveReady = false;
    }

    getConnections(): AutomationPageUiConnectionsController | null {
        return this.#connections;
    }

    cancelPendingScrollShift(): void {
        this.#connections?.cancelPendingScrollShift();
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

export { AutomationPageInteractionController };
