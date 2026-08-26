/* SoAI - Automation routed page [frontend/assets/ts/pages/automation/AutomationPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { shouldPreventDefaultForActionElement } from '@core/dom/dataAction.ts';
import { bindMultiRootPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { optionalTrimmedString } from '@core/types/payloadValueReaders.ts';
import { PageActionsMenuManager } from '@core/pageActionsMenu.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage, type RenderContext } from '@core/StaticBasePage.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import { AUTOMATION_CALENDAR_SETTINGS_MODAL_ID, AUTOMATION_CONFIGURATION_MODAL_ID, AUTOMATION_OCCURRENCE_MODAL_ID, type AutomationRunActivityServiceContract, type AutomationDataService } from '@features/automation/public.ts';
import { isAutomationActionId, type AutomationActionId } from '@pages/automation/actions.ts';
import { AutomationPageController } from '@pages/automation/controllers/AutomationPageController.ts';
import { AutomationUserNotifiedError } from '@pages/automation/controllers/AutomationUserNotifiedError.ts';
import { handleAutomationInitialModal } from '@pages/automation/controllers/initialModal.ts';
import { requireAutomationUi } from '@pages/automation/dom.ts';
import { AutomationInitialRunSelectionController } from '@pages/automation/services/AutomationInitialRunSelectionController.ts';
import type { AutomationInitialSelection, AutomationUiRefs } from '@pages/automation/types.ts';
import { renderAutomationPageView } from '@pages/automation/view.ts';

export const PAGE_ID = 'automation';

interface AutomationPageDependencies {
    dataService: AutomationDataService;
    runActivity: AutomationRunActivityServiceContract;
}

class AutomationPage extends StaticBasePage {
    readonly #dependencies: AutomationPageDependencies;
    #ui: AutomationUiRefs | null = null;
    #controller: AutomationPageController | null = null;
    #initialRunId: string | null = null;
    #initialModal: string | null = null;
    #toolbarOverflowMenu: PageActionsMenuManager | null = null;

    constructor(dependencies: AutomationPageDependencies, basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        this.#dependencies = dependencies;
    }

    override getRequiredResources(): string[] {
        return [];
    }

    override async beforeRender(parameters: JsonObject): Promise<JsonObject> {
        await super.beforeRender(parameters);
        this.#initialRunId = optionalTrimmedString(parameters['run_id']);
        this.#initialModal = optionalTrimmedString(parameters['modal']);
        return {};
    }

    override async renderView(_context: RenderContext): Promise<TrustedHtml> {
        return renderAutomationPageView({
            getIconSync: (iconName, options) => this.services.getIconSync(iconName, options)
        });
    }

    override async setupPage(_parameters: JsonObject | null = null, context: { signal?: AbortSignal } = {}): Promise<void> {
        try {
            const modalPresenter = requireModalPresenter();
            modalPresenter.requireElement(AUTOMATION_CONFIGURATION_MODAL_ID);
            modalPresenter.requireElement(AUTOMATION_CALENDAR_SETTINGS_MODAL_ID);
            modalPresenter.requireElement(AUTOMATION_OCCURRENCE_MODAL_ID);

            const requireHTMLElement = (selector: string, context?: Element | Document | null): HTMLElement => {
                return context instanceof Element ? this.pageDom.requireHTMLElement(selector, context) : this.pageDom.requireHTMLElement(selector);
            };
            const optionalHTMLElement = (selector: string, context?: Element | Document | null): HTMLElement | null => {
                return context instanceof Element ? this.pageDom.optionalHTMLElement(selector, context) : this.pageDom.optionalHTMLElement(selector);
            };
            this.#ui = requireAutomationUi({
                requireHTMLElement,
                optionalHTMLElement
            });

            const dataService = this.#dependencies.dataService;
            const initialSelection = await this.#resolveInitialSelection(dataService);
            if (signalAborted(context.signal ?? this.pageLifecycle.signal() ?? null)) {
                return;
            }

            this.#controller = new AutomationPageController({
                ui: this.#ui,
                storage: this.dependencies.storage,
                api: this.dependencies.api,
                dataService,
                initialSelection,
                runActivity: this.#dependencies.runActivity,
                modalPresenter,
                feedback: this.feedback,
                pageDom: this.pageDom,
                pageLifecycle: this.pageLifecycle,
                pageResources: this.pageResources,
                router: this.dependencies.router,
                services: this.services
            });

            await this.#controller.initializeShell(context.signal ?? null);
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!(runtimeError instanceof AutomationUserNotifiedError)) {
                showOperationFailureNotification({
                    error: runtimeError,
                    showNotification: (message, level): void => this.feedback.show(message, level)
                });
            }
            errorHandler.error('AutomationPage', 'Failed to initialize automation page', runtimeError);
            throw runtimeError;
        }
    }

    bindPageEvents(): void {
        const ui = this.#ui;
        const controller = this.#controller;
        if (!ui || !controller) {
            throw new Error('Automation page UI is not initialized');
        }
        const signal = this.pageLifecycle.beginListeners();
        controller.connect(signal);
        this.#toolbarOverflowMenu?.dispose();
        this.#toolbarOverflowMenu = new PageActionsMenuManager({
            host: {
                on: (target: EventTarget, event: string, handler: EventListener) => this.pageResources.on(target, event, handler)
            },
            breakpoint: 900,
            selectors: {
                wrapper: '.automation-toolbar-overflow',
                trigger: '.automation-toolbar-overflow-trigger',
                menu: '.automation-toolbar-overflow-menu'
            }
        });
        this.#toolbarOverflowMenu.initialize(ui.root);
        const modalPresenter = requireModalPresenter();
        const configurationModal = modalPresenter.requireElement(AUTOMATION_CONFIGURATION_MODAL_ID);
        const calendarSettingsModal = modalPresenter.requireElement(AUTOMATION_CALENDAR_SETTINGS_MODAL_ID);
        this.#wireAutomationModalListeners({ controller, configurationModal, calendarSettingsModal, signal });
        const actionRoots: readonly HTMLElement[] = [ui.root, modalPresenter.requireElement(AUTOMATION_CONFIGURATION_MODAL_ID), modalPresenter.requireElement(AUTOMATION_CALENDAR_SETTINGS_MODAL_ID), modalPresenter.requireElement(AUTOMATION_OCCURRENCE_MODAL_ID)];
        this.#bindAutomationActionEvents({ roots: actionRoots, controller, signal });
        handleAutomationInitialModal({ pageDom: this.pageDom, router: this.dependencies.router }, controller, this.#initialModal);
        this.#initialModal = null;
    }

    override async prepareInitialContent(_parameters: JsonObject, context: { signal?: AbortSignal } = {}): Promise<void> {
        const controller = this.#controller;
        if (!controller) {
            throw new Error('Automation page controller is not initialized');
        }
        await controller.activate(context.signal ?? null);
    }

    #wireAutomationModalListeners(dependencies: { controller: AutomationPageController; configurationModal: HTMLElement; calendarSettingsModal: HTMLElement; signal: AbortSignal }): void {
        const handleConfigurationModalOpen = (): void => dependencies.controller.onConfigurationModalOpen(dependencies.configurationModal);
        dependencies.configurationModal.addEventListener('core.modal.open', handleConfigurationModalOpen, { signal: dependencies.signal });
        const handleConfigurationModalClose = (): void => dependencies.controller.onConfigurationModalClose();
        dependencies.configurationModal.addEventListener('core.modal.close', handleConfigurationModalClose, { signal: dependencies.signal });

        const handleCalendarSettingsModalOpen = (): void => dependencies.controller.onCalendarSettingsModalOpen(dependencies.calendarSettingsModal);
        dependencies.calendarSettingsModal.addEventListener('core.modal.open', handleCalendarSettingsModalOpen, { signal: dependencies.signal });
        const handleCalendarSettingsModalClose = (): void => dependencies.controller.onCalendarSettingsModalClose();
        dependencies.calendarSettingsModal.addEventListener('core.modal.close', handleCalendarSettingsModalClose, { signal: dependencies.signal });
    }

    #bindAutomationActionEvents(dependencies: { roots: readonly HTMLElement[]; controller: AutomationPageController; signal: AbortSignal }): void {
        const onAction = ({ event, action, actionElement }: { event: Event; action: AutomationActionId; actionElement: HTMLElement }): void => {
            this.#dispatchAutomationActionEvent(dependencies.controller, event, action, actionElement);
        };
        bindMultiRootPageActionDispatcher({
            label: 'AutomationPage',
            roots: dependencies.roots,
            signal: dependencies.signal,
            isAction: isAutomationActionId,
            events: {
                click: { mouseButton: 'primary', preventDefault: 'never', onAction },
                change: { preventDefault: 'never', onAction },
                keydown: { preventDefault: 'never', onAction }
            }
        });
    }

    #dispatchAutomationActionEvent(controller: AutomationPageController, event: Event, action: AutomationActionId, actionElement: HTMLElement): void {
        if (event.type === 'change') {
            if (!this.#isAutomationActionFormControl(actionElement)) {
                return;
            }
            controller.handleAction(action, actionElement);
            return;
        }

        if (event.type === 'click') {
            if (this.#isAutomationActionFormControl(actionElement)) {
                return;
            }
            if (shouldPreventDefaultForActionElement(actionElement)) {
                event.preventDefault();
            }
            controller.handleAction(action, actionElement);
            return;
        }

        this.#dispatchAutomationKeyboardAction(controller, event, action, actionElement);
    }

    #dispatchAutomationKeyboardAction(controller: AutomationPageController, event: Event, action: AutomationActionId, actionElement: HTMLElement): void {
        const keyboardEvent = event instanceof KeyboardEvent ? event : null;
        if (!keyboardEvent) {
            return;
        }
        if (keyboardEvent.key !== 'Enter' && keyboardEvent.key !== ' ') {
            return;
        }
        if (actionElement instanceof HTMLButtonElement || this.#isAutomationActionFormControl(actionElement)) {
            return;
        }
        const role = (actionElement.getAttribute('role') ?? '').trim();
        if (role !== 'button') {
            return;
        }
        event.preventDefault();
        controller.handleAction(action, actionElement);
    }

    #isAutomationActionFormControl(actionElement: HTMLElement): boolean {
        return actionElement instanceof HTMLInputElement || actionElement instanceof HTMLSelectElement || actionElement instanceof HTMLTextAreaElement;
    }

    override async onDestroy(): Promise<void> {
        this.pageLifecycle.abortListeners();
        this.#toolbarOverflowMenu?.dispose();
        this.#toolbarOverflowMenu = null;
        this.#controller?.destroy();
        this.#controller = null;
        this.#initialRunId = null;
        this.#initialModal = null;
        this.#ui = null;
    }

    async #resolveInitialSelection(dataService: AutomationDataService): Promise<AutomationInitialSelection | null> {
        try {
            return await AutomationInitialRunSelectionController({
                dataService,
                runId: this.#initialRunId,
                abortSignal: this.pageLifecycle.signal() ?? null
            });
        } catch (error) {
            errorHandler.warn('AutomationPage', 'Failed to resolve initial automation run selection', ensureError(error));
            this.feedback.show(i18n.t('automation.notifications.runOpenFailed'), 'warning');
            return null;
        }
    }
}

export { AutomationPage };
