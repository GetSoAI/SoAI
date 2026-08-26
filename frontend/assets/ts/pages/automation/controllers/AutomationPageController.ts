/* SoAI - Automation page controller [frontend/assets/ts/pages/automation/controllers/AutomationPageController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { ChangeNotificationSource } from '@core/primitives/changeNotificationSource.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import type { AutomationActionId } from '@features/automation/public.ts';
import { AutomationPageActivationController } from '@pages/automation/controllers/AutomationPageActivationController.ts';
import { AutomationCalendarTransitionController } from '@pages/automation/controllers/AutomationCalendarTransitionController.ts';
import { dispatchAutomationPageAction, type AutomationPageActionDispatcherHost } from '@pages/automation/controllers/automationPageActionDispatcher.ts';
import type { ControllerDependencies, ControllerRuntimeDependencies } from '@pages/automation/controllers/contracts.ts';
import { createAutomationPageEnvironment } from '@pages/automation/controllers/AutomationPageRuntime.ts';
import { AutomationPageDataController } from '@pages/automation/controllers/AutomationPageDataController.ts';
import { AutomationPageErrorNotifier } from '@pages/automation/controllers/AutomationPageErrorNotifier.ts';
import { AutomationPageInteractionController } from '@pages/automation/controllers/AutomationPageInteractionController.ts';
import { AutomationPageOperationRunner } from '@pages/automation/controllers/AutomationPageOperationRunner.ts';
import { AutomationPageRealtimeController } from '@pages/automation/controllers/AutomationPageRealtimeController.ts';
import { AutomationPageRenderScheduler } from '@pages/automation/controllers/AutomationPageRenderScheduler.ts';
import { AutomationPreferencesState } from '@pages/automation/controllers/AutomationPreferencesState.ts';
import type { AutomationPageUiConnectionsController } from '@pages/automation/controllers/AutomationPageUiConnectionsController.ts';
import { createInitialAutomationPageState } from '@pages/automation/controllers/automationPageState.ts';
import { resetAutomationPagePreferencesAndRefresh, shiftAutomationPageVisiblePeriod } from '@pages/automation/controllers/effects.ts';
import { AutomationPageViewController } from '@pages/automation/controllers/AutomationPageViewController.ts';
import { AutomationWindowRunsPaneController } from '@pages/automation/controllers/windowrunstoolbar/paneController.ts';
import { AUTOMATION_SPLIT_MAX_PERCENT, AUTOMATION_SPLIT_MIN_PERCENT, persistAutomationPagePreferences } from '@pages/automation/state/preferences.ts';
import type { AutomationPageState } from '@pages/automation/types.ts';
import { AUTOMATION_DEFAULT_HOUR_HEIGHT_PX, AUTOMATION_DEFAULT_MONTH_MAX_ZONES_PER_DAY } from '@pages/automation/widgets/calendar/constants.ts';

class AutomationPageController {
    readonly #dependencies: ControllerRuntimeDependencies;
    readonly #activationController: AutomationPageActivationController;
    readonly #actionHost: AutomationPageActionDispatcherHost;
    readonly #calendarTransition: AutomationCalendarTransitionController;
    readonly #dataController: AutomationPageDataController;
    readonly #errorNotifier: AutomationPageErrorNotifier;
    readonly #interactionController: AutomationPageInteractionController;
    readonly #operationRunner: AutomationPageOperationRunner;
    readonly #renderScheduler: AutomationPageRenderScheduler;
    readonly #realtimeController: AutomationPageRealtimeController;
    readonly #viewController: AutomationPageViewController;
    readonly #windowRunsPane: AutomationWindowRunsPaneController;
    readonly #preferencesStatus = new AutomationPreferencesState();
    readonly #renderRequests = new ChangeNotificationSource();
    readonly #unsubscribeRenderRequests: () => void;
    #connectionSignal: AbortSignal | null = null;
    #destroyed = false;
    #hourHeightPx = AUTOMATION_DEFAULT_HOUR_HEIGHT_PX;
    #monthMaxChipsPerDay = AUTOMATION_DEFAULT_MONTH_MAX_ZONES_PER_DAY;
    #runningAutomationIds: ReadonlySet<string> = new Set();
    #state: AutomationPageState;
    readonly #getState = (): AutomationPageState => this.#state;
    readonly #setState = (next: AutomationPageState): void => {
        this.#state = next;
    };

    constructor(dependencies: ControllerDependencies) {
        this.#dependencies = createAutomationPageEnvironment(dependencies);
        const runtime = this.#dependencies;
        this.#state = createInitialAutomationPageState();
        this.#errorNotifier = new AutomationPageErrorNotifier({ showNotification: runtime.showNotification });
        this.#calendarTransition = new AutomationCalendarTransitionController({
            calendarRoot: dependencies.ui.calendarRoot,
            requestAnimationFrame: (callback) => runtime.requestAnimationFrame(callback)
        });
        this.#operationRunner = new AutomationPageOperationRunner({
            runWithBoundary: runtime.runWithBoundary,
            errorNotifier: this.#errorNotifier
        });
        this.#dataController = new AutomationPageDataController({
            dataService: dependencies.dataService,
            getState: this.#getState,
            setState: this.#setState,
            queueRender: () => this.#renderRequests.notify(),
            isDestroyed: () => this.#destroyed
        });
        this.#realtimeController = new AutomationPageRealtimeController({
            runActivity: dependencies.runActivity,
            getState: this.#getState,
            setState: this.#setState,
            getWindowSignature: () => this.#dataController.getWindowSignature(),
            refreshData: () => this.#dataController.refresh(),
            queueRender: () => this.#renderRequests.notify(),
            getRun: (runId) => dependencies.dataService.getRun(runId),
            setRunningAutomationIds: (next) => {
                this.#runningAutomationIds = next;
            },
            run: (operation, task) => this.#operationRunner.run(operation, task)
        });
        this.#interactionController = new AutomationPageInteractionController({
            initialization: {
                requireHTMLElement: runtime.requireHTMLElement,
                modalPresenter: dependencies.modalPresenter,
                api: dependencies.api,
                dataService: dependencies.dataService,
                getIconSync: runtime.getIconSync,
                getState: this.#getState,
                setState: this.#setState,
                refreshData: () => this.#dataController.refresh(),
                showNotification: runtime.showNotification,
                storage: dependencies.storage,
                isPreferencesCorrupt: () => this.#preferencesStatus.isCorrupt
            },
            ui: dependencies.ui,
            applySplit: (value) => this.#applySplit(value),
            getHourHeightPx: () => this.#hourHeightPx,
            requestAnimationFrame: runtime.requestAnimationFrame,
            setTimeout: runtime.setTimeout,
            clearTimer: runtime.clearTimer,
            setMonthMaxChipsPerDay: (value) => {
                this.#monthMaxChipsPerDay = value;
            },
            queueRender: () => this.#renderRequests.notify(),
            run: (operation, task) => this.#operationRunner.run(operation, task),
            realtimeConnect: (signal) => this.#realtimeController.connect(signal),
            shiftVisiblePeriod: (offset) => this.#shiftVisiblePeriod(offset)
        });
        this.#windowRunsPane = new AutomationWindowRunsPaneController({
            dataService: dependencies.dataService,
            getState: this.#getState,
            setState: this.#setState,
            refreshData: () => this.#dataController.refresh(),
            showNotification: runtime.showNotification,
            queueRender: () => this.#renderRequests.notify(),
            run: (operation, task) => this.#operationRunner.run(operation, task),
            closeOccurrenceModal: () => this.#interactionController.getOccurrenceModal()?.close()
        });
        this.#viewController = new AutomationPageViewController({
            ui: dependencies.ui,
            replaceElementContent: runtime.replaceElementContent,
            flushDOMUpdates: runtime.flushDOMUpdates,
            getIconSync: runtime.getIconSync,
            getHourHeightPx: () => this.#hourHeightPx,
            getMonthMaxChipsPerDay: () => this.#monthMaxChipsPerDay,
            getRunningAutomationIds: () => this.#runningAutomationIds,
            isPreferencesCorrupt: () => this.#preferencesStatus.isCorrupt,
            queueRender: () => this.#renderRequests.notify(),
            windowRunsPane: this.#windowRunsPane,
            getConnections: () => this.#interactionController.getConnections()
        });
        this.#renderScheduler = new AutomationPageRenderScheduler({
            requestAnimationFrame: runtime.requestAnimationFrame,
            runWithBoundary: runtime.runWithBoundary,
            isDestroyed: () => this.#destroyed,
            render: () => {
                this.#calendarTransition.playPending(this.#viewController.render(this.#state));
            },
            errorNotifier: this.#errorNotifier
        });
        this.#unsubscribeRenderRequests = this.#renderRequests.subscribe(() => this.#renderScheduler.queue());
        this.#activationController = new AutomationPageActivationController({
            storage: dependencies.storage,
            root: dependencies.ui.root,
            initialSelection: dependencies.initialSelection,
            getState: this.#getState,
            setState: this.#setState,
            setHourHeightPx: (value) => {
                this.#hourHeightPx = value;
            },
            applySplit: (percent) => this.#applySplit(percent),
            queueRender: () => this.#renderRequests.notify(),
            refreshData: () => this.#dataController.refresh(),
            waitForRenderIdle: () => this.#renderScheduler.waitForIdle(),
            getStyleProp: runtime.getStyleProp,
            showWarningNotification: (message) => runtime.showNotification(message, 'warning'),
            preferencesStatus: this.#preferencesStatus
        });
        this.#actionHost = {
            state: {
                ui: dependencies.ui,
                dataService: dependencies.dataService,
                getState: this.#getState,
                setState: this.#setState,
                persistPreferences: () => persistAutomationPagePreferences(dependencies.storage, this.#state, this.#preferencesStatus.isCorrupt),
                queueRender: () => this.#renderRequests.notify(),
                refreshData: () => this.#dataController.refresh(),
                stageCalendarTransition: (direction, signature, variant = 'standard') => this.#calendarTransition.stage(direction, signature, variant),
                setTimeout: runtime.setTimeout,
                showNotification: runtime.showNotification,
                navigateToConversation: runtime.navigateToConversation
            },
            controllers: {
                getEditor: () => this.#interactionController.getEditor(),
                getCalendarSettings: () => this.#interactionController.getCalendarSettingsController(),
                getOccurrenceModal: () => this.#interactionController.getOccurrenceModal(),
                requestCenterPeriodAfterNextRender: () => this.#requireConnections().requestCenterPeriodAfterNextRender(),
                requestCenterNowLineAfterNextRender: () => this.#requireConnections().requestCenterNowLineAfterNextRender(),
                centerNowLineNow: () => this.#requireConnections().centerNowLineNow(),
                animateVisiblePeriod: (direction) => this.#requireConnections().animateVisiblePeriod(direction),
                run: (operation, task) => this.#operationRunner.run(operation, task),
                isPreferencesCorrupt: () => this.#preferencesStatus.isCorrupt,
                resetPreferences: () => this.#resetPreferences()
            },
            windowRuns: {
                enterWindowRunsSelectMode: () => this.#windowRunsPane.enterSelectMode(),
                exitWindowRunsSelectMode: () => this.#windowRunsPane.exitSelectMode(),
                toggleWindowRunsOccurrenceSelected: (zoneKey) => this.#windowRunsPane.toggleOccurrenceSelected(zoneKey),
                batchDeleteWindowRunsOccurrences: () => this.#windowRunsPane.batchDelete(),
                deleteWindowRunsOccurrence: (zoneKey) => this.#windowRunsPane.deleteOne(zoneKey)
            }
        };
    }

    async initializeShell(signal: AbortSignal | null = null): Promise<void> {
        await this.#activationController.initializeShell();
        throwIfAborted(signal);
        await this.#interactionController.initialize();
    }

    async activate(signal: AbortSignal | null = null): Promise<void> {
        await this.#activationController.activate(signal);
    }
    connect(signal: AbortSignal): void {
        this.#connectionSignal = signal;
        if (signal.aborted || this.#activationController.isPreferencesCorrupt()) {
            return;
        }
        this.#interactionController.connect(signal);
    }
    onConfigurationModalOpen(modal: Element): void {
        this.#interactionController.onConfigurationModalOpen(modal);
    }
    onConfigurationModalClose(): void {
        this.#interactionController.onConfigurationModalClose();
    }

    onCalendarSettingsModalOpen(modal: Element): void {
        this.#interactionController.onCalendarSettingsModalOpen(modal);
    }

    onCalendarSettingsModalClose(): void {
        this.#interactionController.onCalendarSettingsModalClose();
    }

    destroy(): void {
        this.#destroyed = true;
        this.#unsubscribeRenderRequests();
        this.#renderRequests.clear();
        this.#monthMaxChipsPerDay = AUTOMATION_DEFAULT_MONTH_MAX_ZONES_PER_DAY;
        this.#calendarTransition.dispose();
        this.#realtimeController.dispose();
        this.#windowRunsPane.dispose();
        this.#viewController.destroy();
        this.#interactionController.destroy();
        this.#connectionSignal = null;
        this.#activationController.clearPreferencesCorruptError();
    }

    handleAction(actionId: AutomationActionId, element: HTMLElement): void {
        dispatchAutomationPageAction(this.#actionHost, actionId, element);
    }

    #resetPreferences(): void {
        this.#operationRunner.run('automation:preferences:reset', async () => {
            await resetAutomationPagePreferencesAndRefresh({
                storage: this.#dependencies.storage,
                getState: this.#getState,
                setState: this.#setState,
                applySplit: (percent) => this.#applySplit(percent),
                initializeInteractions: () => this.#interactionController.initialize(),
                reconnectInteractions: () => {
                    if (this.#connectionSignal && !this.#connectionSignal.aborted) {
                        this.#interactionController.connect(this.#connectionSignal);
                    }
                },
                queueRender: () => this.#renderRequests.notify(),
                refreshData: () => this.#dataController.refresh(),
                showSuccessNotification: (message) => this.#dependencies.showNotification(message, 'success'),
                clearPreferencesCorruptError: () => this.#preferencesStatus.clear()
            });
        });
    }

    #applySplit(percent: number): void {
        this.#dependencies.ui.root.style.setProperty('--automation-left-width', `${clampNumber(percent, AUTOMATION_SPLIT_MIN_PERCENT, AUTOMATION_SPLIT_MAX_PERCENT)}%`);
    }

    #requireConnections(): AutomationPageUiConnectionsController {
        const connections = this.#interactionController.getConnections();
        if (!connections) {
            throw new Error('Automation page connections are not initialized');
        }
        return connections;
    }

    async #shiftVisiblePeriod(offset: number): Promise<void> {
        await shiftAutomationPageVisiblePeriod(
            {
                getState: this.#getState,
                setState: this.#setState,
                queueRender: () => this.#renderRequests.notify(),
                refreshDataWithBoundary: () => this.#dependencies.runWithBoundary('automation:scrollNavigate', async () => this.#dataController.refresh()),
                cancelPendingScrollShift: () => this.#interactionController.cancelPendingScrollShift(),
                showErrorNotification: (message) => this.#dependencies.showNotification(message, 'error')
            },
            offset
        );
    }
}

export { AutomationPageController };
