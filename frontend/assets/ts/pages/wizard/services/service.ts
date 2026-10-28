/* SoAI - Wizard page service [frontend/assets/ts/pages/wizard/services/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setWizardDisclosureExpanded } from '@pages/wizard/widgets/WizardDisclosureWidget.ts';
import { scrollElementTo } from '@core/scroll.ts';
import { toTrustedUiHtml } from '@core/security/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { dom, optionalHTMLElement } from '@core/dom/dom.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { LifecycleScope } from '@core/lifecycle/lifecycleScope.ts';
import { isAbortError, runWithAbortSignalScope } from '@core/errors/abort.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { awaitPresentationFrame } from '@core/runtime/animationFrames.ts';
import { beginLoadingButtonWithClear } from '@core/ui/loadingbuttons/service.ts';
import { isAiSetupActionId, type WizardActionId } from '@pages/wizard/actions.ts';
import { isAiSetupWizardStepId, requireWizardStepId } from '@pages/wizard/contracts/constants.ts';
import { isWizardAccountFormEligibleForSubmit } from '@pages/wizard/guards/validation.ts';
import type { WizardCompletionDestination, WizardPageServiceHost } from '@pages/wizard/services/contracts.ts';
import { handleWizardAccountInput, handleWizardAccountSubmission } from '@pages/wizard/services/effects.ts';
import { WizardProductAccessController } from '@pages/wizard/services/productAccessController.ts';
import { WizardWelcomeBackgroundController } from '@pages/wizard/services/welcomeBackground.ts';
import { WizardLicensingActionController } from '@pages/wizard/services/WizardLicensingActionController.ts';
import { WizardAiSetupNavigationController } from '@pages/wizard/services/WizardAiSetupNavigationController.ts';
import type { WizardAccountUi } from '@pages/wizard/types.ts';
import { renderWizardStepView } from '@pages/wizard/view.ts';
import type { WizardStatusResponse } from '@core/api/contracts/wizardLicensingContracts.ts';

class WizardPageService {
    #host: WizardPageServiceHost;
    #accountUi: WizardAccountUi | null = null;
    #accountValidationTimerId: number | null = null;
    #welcomeBackground: WizardWelcomeBackgroundController;
    #licensingActions: WizardLicensingActionController;
    #productAccess: WizardProductAccessController;
    readonly #aiNavigator: WizardAiSetupNavigationController;
    readonly #timers = new ResourceTracker();
    readonly #stepScope = new LifecycleScope();

    constructor(host: WizardPageServiceHost) {
        this.#host = host;
        this.#welcomeBackground = new WizardWelcomeBackgroundController({
            isDomUsable: () => this.#host.view.isDomUsable(),
            logWarn: (operation, error) => this.#host.completion.logWarn(operation, error)
        });
        this.#licensingActions = new WizardLicensingActionController(host, (index, options) => {
            const showOptions = options?.focusHeading === undefined ? { showNextLoading: false } : { showNextLoading: false, focusHeading: options.focusHeading };
            return this.showStep(index, showOptions);
        });
        this.#productAccess = new WizardProductAccessController({
            host,
            clearSensitiveInput: () => this.#licensingActions.clearProductKey(),
            clearInlineError: () => this.#licensingActions.clearInlineError()
        });
        this.#aiNavigator = new WizardAiSetupNavigationController({
            state: host.view.state,
            flow: host.aiSetup,
            showStep: (index, options) => this.showStep(index, options),
            completeWizard: (destination) => this.completeWizard(destination),
            navigate: (destination) => this.#host.completion.navigateAfterCompletion(false, destination),
            syncNavigation: () => this.#host.view.syncCurrentNavigation()
        });
    }
    get aiNavigator(): WizardAiSetupNavigationController {
        return this.#aiNavigator;
    }
    destroy(): void {
        this.#stepScope.abort('wizard-destroy');
        this.#productAccess.invalidate();
        this.#welcomeBackground.stop();
        this.#clearAccountValidationTimer();
        this.#timers.cleanup();
        this.#accountUi = null;
        this.#licensingActions.invalidate();
        this.#host.aiSetup.destroy();
    }
    readonly showStep = async (index: number, options: { showNextLoading: boolean; focusHeading?: boolean } = { showNextLoading: false }): Promise<void> => {
        if (!this.#host.view.isDomUsable()) {
            return;
        }
        const stepId = requireWizardStepId(this.#host.view.state.steps, clampNumber(index, 0, this.#host.view.state.steps.length - 1));
        const aiStep = isAiSetupWizardStepId(stepId) ? stepId : null;
        const run = this.#stepScope.begin('wizard-step-superseded');
        const ui = this.#host.view.requireUi();

        const clearLoading = options.showNextLoading ? beginLoadingButtonWithClear(ui.navNextButton) : null;

        try {
            if (stepId === 'license') {
                await this.#licensingActions.ensureLicenseTextLoaded();
            }

            if (stepId === 'product_access') {
                await this.#productAccess.loadDocuments();
            }

            if (aiStep !== null || stepId === 'complete') {
                await this.#host.aiSetup.prepareStep(aiStep ?? 'complete');
            }

            if (!this.#stepScope.isCurrent(run) || !this.#host.view.isDomUsable()) return;
            const stepIndex = this.#host.view.state.steps.indexOf(stepId);
            if (stepIndex < 0) return this.showStep(index, options);

            this.#welcomeBackground.stop();
            this.#productAccess.invalidate();
            this.#clearAccountValidationTimer();
            this.#host.view.state.stepIndex = stepIndex;
            const aiSetup = aiStep !== null || stepId === 'complete' ? this.#host.aiSetup.buildViewModel(aiStep ?? 'complete') : null;
            const html = renderWizardStepView(stepId, { ...this.#host.view.createViewContext(), aiSetup });
            ui.content.dataset['step'] = stepId;
            const wizardMarkup = toTrustedUiHtml(html);
            this.#host.view.updateHTML(ui.content, wizardMarkup);
            dom.flush();
            if (aiStep === null) this.#host.aiSetup.stepUi.detach();
            else this.#host.aiSetup.afterRender(aiStep, ui.content);
            if (options.focusHeading === true) {
                const heading = optionalHTMLElement(dom.resolve('h2', ui.content), 'Wizard step heading');
                if (heading !== null) {
                    heading.tabIndex = -1;
                    heading.focus({ preventScroll: true });
                }
            }
            this.#host.completion.refreshLogos();
            this.#accountUi = stepId === 'account' ? this.#host.view.requireAccountUi() : null;
            if (stepId !== 'product_access') this.#licensingActions.clearProductKey();

            if (stepId === 'welcome') {
                this.#host.view.syncWelcomeLanguageFlag(ui.content);
                this.#welcomeBackground.start(ui.content);
            }

            this.#host.view.updateProgress(ui);
            this.#host.view.syncNavigation(ui, stepId);
            await runWithAbortSignalScope([run.signal, this.#host.view.getAbortSignal()], (signal) => awaitPresentationFrame(signal, 'Wizard step rendering was interrupted'));
            if (!this.#stepScope.isCurrent(run) || !this.#host.view.isDomUsable()) return;
            scrollElementTo(ui.content, { top: 0 });
        } catch (error) {
            if (!isAbortError(error)) throw error;
        } finally {
            if (clearLoading !== null) {
                clearLoading();
                if (this.#host.view.isDomUsable()) this.#host.view.syncCurrentNavigation();
            }
        }
    };
    async handleNext(): Promise<void> {
        if (this.#host.view.state.isBusy) {
            return;
        }

        const stepId = requireWizardStepId(this.#host.view.state.steps, this.#host.view.state.stepIndex);
        switch (stepId) {
            case 'welcome':
                await this.showStep(1, { showNextLoading: true });
                return;
            case 'license':
                await this.#licensingActions.mutate(
                    async (status) => this.#host.data.acceptLicense(status),
                    async () => this.showStep(this.#host.view.state.stepIndex + 1, { showNextLoading: true })
                );
                return;
            case 'use': {
                const declaration = this.#host.view.state.declarationSelection;
                if (declaration === null || (declaration === 'personal' && !this.#host.view.state.attestationConfirmed)) return;
                await this.#licensingActions.mutate(
                    async (status) => this.#host.data.declareUse(status, declaration, this.#host.view.state.attestationConfirmed),
                    async (status) => {
                        const nextIndex = this.#host.view.state.steps.indexOf(status.resumeStep);
                        await this.showStep(nextIndex < 0 ? this.#host.view.state.stepIndex + 1 : nextIndex);
                    }
                );
                return;
            }
            case 'product_access':
                return;
            case 'account':
                this.#clearAccountValidationTimer();
                if (!this.#isAccountSubmitEligible()) {
                    this.#host.view.syncNavigation(this.#host.view.requireUi(), 'account');
                    return;
                }
                await handleWizardAccountSubmission(this.#host, this.#requireAccountUi(), () => this.showStep(Math.min(this.#host.view.state.stepIndex + 1, this.#host.view.state.steps.length - 1), { showNextLoading: false, focusHeading: true }));
                return;
            case 'ai_sources':
            case 'ai_connect':
            case 'ai_models':
            case 'ai_progress':
                await this.#withNextLoading(() => this.#aiNavigator.next(stepId));
                return;
            case 'complete':
                await this.#withNextLoading(() => this.#aiNavigator.completeFromSummary());
                return;
            default:
                throw new Error(`WizardPage: unknown step "${stepId}"`);
        }
    }
    async handleBack(): Promise<void> {
        if (this.#host.view.state.isBusy) {
            return;
        }
        await this.showStep(this.#host.view.state.stepIndex - 1);
    }
    readonly completeWizard = async (destination: WizardCompletionDestination): Promise<void> => {
        await this.#host.data.persistWizardState();
        await this.#host.data.markWizardFirstRunModalsPending();
        this.#host.completion.dispatchWizardCompleted();
        await this.#host.completion.navigateAfterCompletion(this.#host.view.state.isSessionActivationRequired, destination);
    };

    async applyObservedStatus(status: WizardStatusResponse): Promise<void> {
        this.#productAccess.invalidate();
        await this.#licensingActions.applyObservedStatus(status);
    }
    handleInput(source: EventTarget | null): void {
        const stepId = requireWizardStepId(this.#host.view.state.steps, this.#host.view.state.stepIndex);
        if (stepId === 'use') {
            this.#handleUseInput(source);
            return;
        }
        if (isAiSetupWizardStepId(stepId)) {
            this.#host.aiSetup.interactions.handleInput(source);
            return;
        }
        if (stepId === 'product_access') {
            if (source instanceof HTMLInputElement && source.name === 'wizard-product-access') {
                this.#runAsync('product access selection', this.#productAccess.handleSelection(source));
                return;
            }
            this.#licensingActions.handleInput(source);
            this.#host.view.syncNavigation(this.#host.view.requireUi(), 'product_access');
            return;
        }
        if (stepId !== 'account') {
            return;
        }
        const shouldValidateUsername = source instanceof HTMLInputElement && source.id === 'admin-username';
        this.#clearAccountValidationTimer();
        this.#host.view.syncNavigation(this.#host.view.requireUi(), 'account');
        this.#accountValidationTimerId = this.#timers.setTimeout(() => {
            this.#accountValidationTimerId = null;
            if (requireWizardStepId(this.#host.view.state.steps, this.#host.view.state.stepIndex) !== 'account') {
                return;
            }
            const account = this.#requireAccountUi();
            handleWizardAccountInput(this.#host, account, { validateUsername: shouldValidateUsername });
        }, 250);
    }
    handleAiSetupSubmit(form: HTMLFormElement): void {
        if (isAiSetupWizardStepId(requireWizardStepId(this.#host.view.state.steps, this.#host.view.state.stepIndex))) this.#host.aiSetup.interactions.handleSubmit(form);
    }
    #runAsync(operation: string, task: Promise<void>): void {
        void task.catch((error) => {
            const runtimeError = ensureError(error);
            this.#host.completion.logError(`WizardPage: ${operation}`, runtimeError);
        });
    }
    executeAction(action: WizardActionId, source: HTMLElement): void {
        if (isAiSetupActionId(action)) {
            this.#host.aiSetup.interactions.execute(action, source);
            return;
        }
        switch (action) {
            case 'wizard-toggle-disclosure':
                setWizardDisclosureExpanded(source, source.getAttribute('aria-expanded') !== 'true');
                return;
            case 'wizard-back':
                this.#runAsync('wizard-back', this.handleBack());
                return;
            case 'wizard-next':
                this.#runAsync('wizard-next', this.handleNext());
                return;
            case 'wizard-activate':
            case 'wizard-activate-evaluation':
            case 'wizard-reconcile':
            case 'wizard-export-offline':
            case 'wizard-import-offline':
            case 'wizard-start-evaluation':
                this.#licensingActions.execute(action, source);
                return;
            case 'wizard-ai-finish-later':
                this.#runAsync('wizard-ai-finish-later', this.#aiNavigator.finishLater());
                return;
            case 'wizard-ai-skip':
                this.#runAsync('wizard-ai-skip', this.#aiNavigator.skip());
                return;
            default: {
                const exhaustive: never = action;
                throw new Error(`WizardPage: unhandled action "${String(exhaustive)}"`);
            }
        }
    }
    #requireAccountUi(): WizardAccountUi {
        if (this.#accountUi) return this.#accountUi;
        throw new Error('WizardPage: account UI is unavailable');
    }
    #isAccountSubmitEligible(): boolean {
        return isWizardAccountFormEligibleForSubmit(this.#requireAccountUi().form);
    }
    async #withNextLoading(operation: () => Promise<void>): Promise<void> {
        const ui = this.#host.view.requireUi();
        const clearLoading = beginLoadingButtonWithClear(ui.navNextButton);
        try {
            await operation();
        } finally {
            clearLoading();
            if (this.#host.view.isDomUsable()) this.#host.view.syncCurrentNavigation();
        }
    }
    #clearAccountValidationTimer(): void {
        if (this.#accountValidationTimerId === null) return;
        this.#timers.clearTimer(this.#accountValidationTimerId);
        this.#accountValidationTimerId = null;
    }
    #handleUseInput(source: EventTarget | null): void {
        if (source instanceof HTMLInputElement && source.name === 'wizard-use') {
            if (source.value === 'personal' || source.value === 'organization_commercial') {
                this.#host.view.state.declarationSelection = source.value;
                if (source.value !== 'personal') this.#host.view.state.attestationConfirmed = false;
                const ui = this.#host.view.requireUi();
                this.#host.view.syncUseSelection(ui);
                this.#host.view.syncNavigation(ui, 'use');
            }
            return;
        }
        if (source instanceof HTMLInputElement && source.id === 'wizard-personal-attestation') {
            this.#host.view.state.attestationConfirmed = source.checked;
            this.#host.view.syncNavigation(this.#host.view.requireUi(), 'use');
        }
    }
}
export { WizardPageService };
