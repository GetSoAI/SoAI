/* SoAI - Updates page workflow controller [frontend/assets/ts/pages/updates/controllers/UpdatesPageWorkflowController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import type { UpdatesPageDependencies } from '@pages/updates/contracts/contracts.ts';
import type { UpdatesPageActionHandlers } from '@pages/updates/controllers/events.ts';
import type { UpdatesInstallOutcome, UpdatesOperationOutcome, UpdatesProductController, UpdatesProductRuntimeDependencies } from '@core/edition/updatesContribution.ts';
import type { UpdatesControllerNoticeSurface } from '@pages/updates/controllers/contracts.ts';
import { applyCheckOutcomeNotice, applyCheckingUpdatesNotice, applyInstallOutcomeNotice, applyInstallStartedNotice, applyOperationTimeoutNotice, resolveUpdatesCheckNotification } from '@pages/updates/controllers/updatesPageNoticeController.ts';
import { executeApplicationInstallWorkflow, executeUpdatesCheckWorkflow } from '@pages/updates/controllers/updatesPageOperationsController.ts';
import { UpdatesOperationMonitor } from '@pages/updates/controllers/updatesOperationMonitorController.ts';
import { createUpdatesSystemControllerHost, type UpdatesPageControllerHostDependencies } from '@pages/updates/controllers/updatesPageHostController.ts';
import type { UpdatesSystemController } from '@pages/updates/controllers/UpdatesSystemController.ts';
import type { UpdatesSystemControllerHost } from '@pages/updates/controllers/UpdatesSystemControllerContract.ts';
import type { UpdatesUiRefs } from '@pages/updates/types.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { PageContext } from '@core/pagecontext/public.ts';
import type { StateManager } from '@core/state/StateManager.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { narrowButton } from '@core/dom/narrowElement.ts';
import { isFunction } from '@core/typeGuards.ts';
import { hoursToMs } from '@core/time/durations.ts';

const UPDATE_OPERATION_TIMEOUT_MS = hoursToMs(2);

interface UpdatesPageWorkflowControllerDependencies {
    restartOverlay: UpdatesPageDependencies['restartOverlay'];
    api: ApiClient;
    pageResources: PageResources;
    feedback: PageFeedback;
    pageElements: PageUi;
    pageDom: PageDom;
    pageContext: PageContext;
    services: PageServices;
    stateManager: StateManager;
    streaming: PageStreaming;
    storage: StorageService;
}

class UpdatesPageWorkflowController {
    readonly #dependencies: UpdatesPageWorkflowControllerDependencies;
    readonly #operationMonitor: UpdatesOperationMonitor;
    #ui: UpdatesUiRefs | null = null;
    #systemController: UpdatesSystemController | null = null;
    #productController: UpdatesProductController | null = null;
    #checkingUpdates = false;

    constructor(dependencies: UpdatesPageWorkflowControllerDependencies) {
        this.#dependencies = dependencies;
        this.#operationMonitor = new UpdatesOperationMonitor(
            {
                setTimeout: (callback, delay) => dependencies.pageResources.setTimeout(callback, delay),
                clearTimer: (timerId) => dependencies.pageResources.clearTimer(timerId),
                onTimeout: () => this.#withNoticeUi((ui) => applyOperationTimeoutNotice(this.#createNoticeHost(), ui))
            },
            UPDATE_OPERATION_TIMEOUT_MS
        );
    }

    setUi(ui: UpdatesUiRefs): void {
        this.#ui = ui;
    }

    setControllers(systemController: UpdatesSystemController, productController: UpdatesProductController | null): void {
        this.#systemController = systemController;
        this.#productController = productController;
    }

    createSystemHost(): UpdatesSystemControllerHost {
        return createUpdatesSystemControllerHost(this.#createControllerHostDependencies());
    }

    createActionHandlers(): UpdatesPageActionHandlers {
        return {
            onCheckUpdates: async () => await this.#checkForUpdates(),
            onInstallSystemUpdate: async (button) => await this.#onInstallSystemUpdate(button)
        };
    }

    cleanup(): void {
        this.#productController?.destroy();
        this.#productController = null;
        this.#systemController?.destroy();
        this.#systemController = null;
        this.#ui = null;
        this.#checkingUpdates = false;
        this.#operationMonitor.invalidate();
    }

    async #checkForUpdates(): Promise<void> {
        if (this.#checkingUpdates) {
            return;
        }
        const checkButton = this.#resolveCheckButton();
        this.#checkingUpdates = true;
        try {
            await executeUpdatesCheckWorkflow({
                checkButton,
                systemController: this.#requireSystemController(),
                productController: this.#productController,
                beginOperation: () => this.#operationMonitor.begin(),
                finishOperation: (operationRevision) => this.#operationMonitor.finish(operationRevision),
                setButtonLoading: (button, loading) => this.#setButtonLoading(button, loading),
                applyCheckingNotice: () => this.#withNoticeUi((ui) => applyCheckingUpdatesNotice(this.#createNoticeHost(), ui)),
                applyCheckResults: (operationRevision, applicationResult, productResult) => this.#applyCheckResults(operationRevision, applicationResult, productResult)
            });
        } finally {
            this.#checkingUpdates = false;
        }
    }

    async #onInstallSystemUpdate(button: HTMLButtonElement): Promise<void> {
        await executeApplicationInstallWorkflow({
            button,
            systemController: this.#requireSystemController(),
            completeInstall: (outcome) => this.#onInstallCompleted(outcome, outcome.operationRevision)
        });
    }

    #createControllerHostDependencies(): UpdatesPageControllerHostDependencies {
        return {
            checkUpdates: async () => await this.#dependencies.api.software.checkUpdates(),
            updateSoAI: async () => await this.#dependencies.api.software.updateSoAI(),
            systemSurface: {
                notify: (message, type) => this.#dependencies.feedback.show(message, type ?? 'info'),
                setButtonLoading: (button, loading, options) => this.#setButtonLoading(button, loading, options),
                handleError: (error, context, options) => this.#dependencies.feedback.handle(error, context, options),
                toggleHidden: (element, hidden) => this.#dependencies.pageElements.toggleHidden(element, hidden),
                updateText: (element, text) => this.#dependencies.pageDom.updateText(element, text),
                updateHTML: (element, html, options) => this.#dependencies.pageDom.updateHtml(element, html, options),
                updateProperty: (element, property, value) => this.#dependencies.pageDom.updateProperty(element, property, value),
                updateCheckerboard: () => this.#dependencies.pageElements.updateCheckerboard(),
                sanitizeHtml: (value) => this.#dependencies.pageContext.sanitizer.html(value),
                sanitizeAttribute: (value) => this.#dependencies.pageContext.sanitizer.attribute(value),
                sanitizeUrl: (value, options) => this.#dependencies.pageContext.sanitizer.url(value, options),
                getIconSync: (name, options) => this.#dependencies.services.getIconSync(name, options),
                showOverlay: (value) => this.#dependencies.restartOverlay.show(value),
                resolveInstallButton: () => this.#resolveInstallButton(),
                wait: (milliseconds) => this.#wait(milliseconds)
            },
            onApplicationInstallStarted: () => this.#onInstallStarted()
        };
    }

    createProductRuntimeDependencies(): UpdatesProductRuntimeDependencies {
        const productApi = this.#dependencies.api.os;
        if (productApi === null) {
            throw new Error('Trusted host update API is unavailable for the selected frontend edition');
        }
        return {
            api: productApi,
            storage: this.#dependencies.storage,
            pageResources: this.#dependencies.pageResources,
            feedback: this.#dependencies.feedback,
            pageElements: this.#dependencies.pageElements,
            pageDom: this.#dependencies.pageDom,
            pageContext: this.#dependencies.pageContext,
            services: this.#dependencies.services,
            stateManager: this.#dependencies.stateManager,
            streaming: this.#dependencies.streaming,
            onInstallStarted: () => this.#onInstallStarted(),
            onInstallCompleted: (outcome, operationRevision) => this.#onInstallCompleted(outcome, operationRevision)
        };
    }

    #createNoticeHost(): UpdatesControllerNoticeSurface {
        return {
            updateText: (element, text) => this.#dependencies.pageDom.updateText(element, text),
            toggleHidden: (element, hidden) => this.#dependencies.pageElements.toggleHidden(element, hidden)
        };
    }

    #withNoticeUi(action: (ui: UpdatesUiRefs) => void): void {
        const ui = this.#ui;
        if (ui) {
            action(ui);
        }
    }

    #applyCheckResults(operationRevision: number, applicationResult: UpdatesOperationOutcome, osResult: UpdatesOperationOutcome): void {
        if (!this.#operationMonitor.isCurrent(operationRevision)) {
            return;
        }
        if (this.#operationMonitor.hasTimedOut(operationRevision) && applicationResult.type !== 'error' && osResult.type !== 'error') {
            return;
        }
        this.#withNoticeUi((ui) => applyCheckOutcomeNotice(this.#createNoticeHost(), ui, applicationResult, osResult));
        const notification = resolveUpdatesCheckNotification(applicationResult, osResult);
        if (notification) {
            this.#dependencies.feedback.show(notification.message, notification.type);
        }
    }

    #onInstallStarted(): number {
        const operationRevision = this.#operationMonitor.begin();
        this.#withNoticeUi((ui) => applyInstallStartedNotice(this.#createNoticeHost(), ui));
        return operationRevision;
    }

    #onInstallCompleted(outcome: UpdatesInstallOutcome, operationRevision: number | null): void {
        if (operationRevision === null && outcome.type !== 'error') {
            return;
        }
        if (operationRevision !== null && !this.#operationMonitor.finishAndCanApply(operationRevision, outcome.type === 'error')) {
            return;
        }
        this.#withNoticeUi((ui) => applyInstallOutcomeNotice(this.#createNoticeHost(), ui, outcome));
    }

    #requireSystemController(): UpdatesSystemController {
        if (!this.#systemController) {
            throw new Error('UpdatesSystemController was not initialized');
        }
        return this.#systemController;
    }

    #resolveCheckButton(): HTMLButtonElement {
        return narrowButton(this.#dependencies.pageDom.requireHTMLElement('#checkUpdatesBtn'), '#checkUpdatesBtn');
    }

    #resolveInstallButton(): HTMLButtonElement | null {
        const button = this.#dependencies.pageDom.optional('#installUpdateBtn');
        return button instanceof HTMLButtonElement ? button : null;
    }

    async #wait(milliseconds: number): Promise<void> {
        const deferred = createDeferred<void>();
        this.#dependencies.pageResources.setTimeout(() => deferred.resolve(), Math.max(0, milliseconds));
        await deferred.promise;
    }

    #setButtonLoading(button: HTMLElement, loading: boolean, options?: import('@core/state/UIStateManager.ts').SetButtonLoadingOptions): void {
        if (isFunction(this.#dependencies.stateManager.setButtonLoading)) this.#dependencies.stateManager.setButtonLoading(button, loading, options);
    }
}

export { UpdatesPageWorkflowController };
