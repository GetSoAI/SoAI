/* SoAI - Wizard page service [frontend/assets/ts/pages/wizard/services/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { dom, optionalHTMLElement } from '@core/dom/dom.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { beginLoadingButton, clearLoadingButtonIfNeeded } from '@core/ui/loadingbuttons/service.ts';
import type { WizardActionId } from '@pages/wizard/actions.ts';
import { requireWizardStepId } from '@pages/wizard/contracts/constants.ts';
import { isWizardAccountFormEligibleForSubmit } from '@pages/wizard/guards/validation.ts';
import type { WizardPageServiceHost } from '@pages/wizard/services/contracts.ts';
import { handleWizardAccountInput, handleWizardAccountSubmission } from '@pages/wizard/services/effects.ts';
import { WizardProductAccessController } from '@pages/wizard/services/productAccessController.ts';
import { WizardWelcomeBackgroundController } from '@pages/wizard/services/welcomeBackground.ts';
import { WizardLicensingActionController } from '@pages/wizard/services/WizardLicensingActionController.ts';
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
    readonly #timers = new ResourceTracker();
    #lifecycleRevision = 0;

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
    }
    destroy(): void {
        this.#lifecycleRevision += 1;
        this.#productAccess.invalidate();
        this.#welcomeBackground.stop();
        this.#clearAccountValidationTimer();
        this.#timers.cleanup();
        this.#accountUi = null;
        this.#licensingActions.invalidate();
    }
    executeAction(action: WizardActionId, source: HTMLElement): void {
        this.#dispatchAction(action, source);
    }
    readonly showStep = async (index: number, options: { showNextLoading: boolean; focusHeading?: boolean } = { showNextLoading: false }): Promise<void> => {
        if (!this.#host.view.isDomUsable()) {
            return;
        }
        const stepIndex = clampNumber(index, 0, this.#host.view.state.steps.length - 1);
        const stepId = requireWizardStepId(this.#host.view.state.steps, stepIndex);
        const lifecycleRevision = this.#lifecycleRevision + 1;
        this.#lifecycleRevision = lifecycleRevision;
        const ui = this.#host.view.requireUi();

        if (options.showNextLoading) {
            beginLoadingButton(ui.navNextButton);
        }

        try {
            if (stepId === 'license') {
                await this.#ensureLicenseTextLoaded();
            }

            if (stepId === 'product_access') {
                await this.#productAccess.loadDocuments();
            }

            if (lifecycleRevision !== this.#lifecycleRevision || !this.#host.view.isDomUsable()) return;

            this.#welcomeBackground.stop();
            this.#productAccess.invalidate();
            this.#clearAccountValidationTimer();
            this.#host.view.state.stepIndex = stepIndex;
            const html = renderWizardStepView(stepId, this.#host.view.createViewContext());
            ui.content.dataset['step'] = stepId;
            const wizardMarkup = toTrustedUiHtml(html);
            this.#host.view.updateHTML(ui.content, wizardMarkup);
            if (options.focusHeading === true) {
                const heading = optionalHTMLElement(dom.resolve('h2', ui.content), 'Wizard step heading');
                if (heading !== null) {
                    heading.tabIndex = -1;
                    heading.focus();
                }
            }
            this.#host.completion.refreshLogos();
            this.#accountUi = stepId === 'account' ? this.#host.view.requireAccountUi() : null;
            if (stepId !== 'product_access') this.#licensingActions.clearProductKey();

            if (stepId === 'welcome') {
                this.#welcomeBackground.start(ui.content);
            }

            this.#host.view.updateProgress(ui);
            this.#host.view.syncNavigation(ui, stepId);
        } finally {
            if (options.showNextLoading) {
                clearLoadingButtonIfNeeded(ui.navNextButton);
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
                if (await this.#handleAccountSubmission()) {
                    await this.showStep(Math.min(this.#host.view.state.stepIndex + 1, this.#host.view.state.steps.length - 1));
                }
                return;
            case 'complete':
                await this.#completeWizardFromButton();
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
    async completeWizard(): Promise<void> {
        await this.#host.data.persistWizardState();
        await this.#host.data.markWizardFirstRunModalsPending();
        this.#host.completion.dispatchWizardCompleted();
        await this.#host.completion.navigateAfterCompletion(this.#host.view.state.isSessionActivationRequired);
    }

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
        this.#accountValidationTimerId = this.#timers.setTimeout(() => {
            this.#accountValidationTimerId = null;
            if (requireWizardStepId(this.#host.view.state.steps, this.#host.view.state.stepIndex) !== 'account') {
                return;
            }
            const ui = this.#host.view.requireUi();
            const account = this.#requireAccountUi();
            handleWizardAccountInput(this.#host, account, { validateUsername: shouldValidateUsername });
            this.#host.view.syncNavigation(ui, 'account');
        }, 500);
    }
    #runAsync(operation: string, task: Promise<void>): void {
        void task.catch((error) => {
            const runtimeError = ensureError(error);
            this.#host.completion.logError(`WizardPage: ${operation}`, runtimeError);
        });
    }
    #dispatchAction(action: WizardActionId, source: HTMLElement): void {
        switch (action) {
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
            default: {
                const exhaustive: never = action;
                throw new Error(`WizardPage: unhandled action "${String(exhaustive)}"`);
            }
        }
    }
    async #handleAccountSubmission(): Promise<boolean> {
        const account = this.#requireAccountUi();
        return handleWizardAccountSubmission(this.#host, account);
    }
    #requireAccountUi(): WizardAccountUi {
        if (this.#accountUi) return this.#accountUi;
        throw new Error('WizardPage: account UI is unavailable');
    }
    #isAccountSubmitEligible(): boolean {
        return isWizardAccountFormEligibleForSubmit(this.#requireAccountUi().form);
    }
    async #completeWizardFromButton(): Promise<void> {
        const ui = this.#host.view.requireUi();
        beginLoadingButton(ui.navNextButton);
        try {
            await this.completeWizard();
        } finally {
            clearLoadingButtonIfNeeded(ui.navNextButton);
        }
    }
    #clearAccountValidationTimer(): void {
        if (this.#accountValidationTimerId === null) return;
        this.#timers.clearTimer(this.#accountValidationTimerId);
        this.#accountValidationTimerId = null;
    }
    async #ensureLicenseTextLoaded(): Promise<void> {
        if (this.#host.view.state.licenseText.length > 0) return;
        this.#host.view.state.licenseText = await this.#host.data.fetchLicenseText();
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
