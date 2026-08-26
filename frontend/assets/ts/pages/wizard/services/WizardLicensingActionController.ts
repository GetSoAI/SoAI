/* SoAI - Wizard licensing mutation and product-access lifecycle [frontend/assets/ts/pages/wizard/services/WizardLicensingActionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WizardStatusResponse } from '@core/api/contracts/wizardLicensingContracts.ts';
import { licensingLegalAcceptances } from '@core/api/contracts/licensingRequestSerialization.ts';
import { dom, optionalHTMLElement, optionalInput } from '@core/dom/dom.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { presentLicensingError } from '@core/licensing/errorPresentation.ts';
import { presentLicensingOperationState } from '@core/licensing/operationPresentation.ts';
import { isLicensingOperationInProgress } from '@core/licensing/operationLifecycle.ts';
import { beginLoadingButton, clearLoadingButtonIfNeeded } from '@core/ui/loadingbuttons/service.ts';
import { requireWizardStepId } from '@pages/wizard/contracts/constants.ts';
import type { WizardPageServiceHost } from '@pages/wizard/services/contracts.ts';
import { readWizardOrganization } from '@pages/wizard/guards/validation.ts';

type LicensingAction = 'wizard-activate' | 'wizard-activate-evaluation' | 'wizard-reconcile' | 'wizard-export-offline' | 'wizard-import-offline' | 'wizard-start-evaluation';

class WizardLicensingActionController {
    readonly #host: WizardPageServiceHost;
    readonly #showStep: (index: number, options?: { focusHeading?: boolean }) => Promise<void>;
    #revision = 0;

    constructor(host: WizardPageServiceHost, showStep: (index: number, options?: { focusHeading?: boolean }) => Promise<void>) {
        this.#host = host;
        this.#showStep = showStep;
    }

    invalidate(): void {
        this.#revision += 1;
        this.#host.data.invalidateLicensingRequests();
        this.#host.view.state.isBusy = false;
        this.clearProductKey();
    }

    execute(action: LicensingAction, source: HTMLElement): void {
        const operations: Record<LicensingAction, () => Promise<void> | void> = {
            'wizard-activate': () => this.#activate(source),
            'wizard-activate-evaluation': () => this.#activateEvaluation(source),
            'wizard-reconcile': () => this.#reconcile(source),
            'wizard-export-offline': () => this.#exportOffline(source),
            'wizard-import-offline': () => this.#openOfflineChooser(),
            'wizard-start-evaluation': () => this.#startEvaluation(source)
        };
        void Promise.resolve(operations[action]()).catch((error) => this.#host.completion.logError(`WizardPage: ${action}`, ensureError(error)));
    }

    handleInput(source: EventTarget | null): void {
        if (!(source instanceof HTMLInputElement || source instanceof HTMLSelectElement)) return;
        if (source instanceof HTMLInputElement && source.id === 'wizard-offline-certificate') {
            const file = source.files?.[0] ?? null;
            source.value = '';
            if (file !== null) void this.#importOffline(file).catch((error) => this.#host.completion.logError('WizardPage: wizard-import-offline', ensureError(error)));
            return;
        }
        if (source instanceof HTMLInputElement && source.id === 'wizard-evaluation-acknowledgement') this.#host.view.state.evaluationAcknowledged = source.checked;
        this.#syncControls();
        this.#syncNavigation();
    }

    async mutate(operation: (status: WizardStatusResponse) => Promise<WizardStatusResponse>, afterCommit?: (status: WizardStatusResponse) => Promise<void>): Promise<boolean> {
        if (this.#host.view.state.isBusy) return false;
        const revision = this.#revision + 1;
        this.#revision = revision;
        this.#host.view.state.isBusy = true;
        this.#host.view.state.inlineError = null;
        this.#syncControls();
        this.#syncInlineError();
        this.#syncNavigation();
        try {
            let status: WizardStatusResponse;
            try {
                status = await operation(this.#requireStatus());
            } catch (error) {
                if (revision !== this.#revision) return false;
                const mutationError = ensureError(error);
                try {
                    await this.#resynchronizeAfterMutationFailure(revision);
                } catch (resynchronizationError) {
                    this.#host.view.state.inlineError = presentLicensingError(mutationError);
                    this.#syncInlineError();
                    throw new AggregateError([mutationError, ensureError(resynchronizationError)], 'Wizard licensing mutation failed and authoritative state could not be restored');
                }
                this.#host.view.state.inlineError = presentLicensingError(mutationError);
                this.#syncInlineError();
                throw mutationError;
            }
            if (revision !== this.#revision) return false;
            this.#host.data.applyStatus(status);
            if (requireWizardStepId(this.#host.view.state.steps, this.#host.view.state.stepIndex) === 'product_access') this.#syncOperationBanner(status);
            if (afterCommit !== undefined) await afterCommit(status);
            return true;
        } finally {
            if (revision === this.#revision) {
                this.#host.view.state.isBusy = false;
                this.#syncControls();
                this.#syncNavigation();
            }
        }
    }

    async applyObservedStatus(status: WizardStatusResponse): Promise<void> {
        const priorStepId = requireWizardStepId(this.#host.view.state.steps, this.#host.view.state.stepIndex);
        const priorProductAccessFlow = priorStepId === 'product_access' ? this.#host.view.selectedProductAccessFlow(this.#host.view.requireUi()) : null;
        const priorAuthoritativeFlow = this.#host.view.state.status?.selectedProductAccessFlow ?? null;
        this.#host.data.applyStatus(status);
        const retainedIndex = this.#host.view.state.steps.indexOf(priorStepId);
        if (retainedIndex < 0) {
            const resumeIndex = this.#host.view.state.steps.indexOf(status.resumeStep);
            const accountIndex = this.#host.view.state.steps.indexOf('account');
            await this.#showStep(resumeIndex >= 0 ? resumeIndex : accountIndex, { focusHeading: true });
            return;
        }
        this.#host.view.state.stepIndex = retainedIndex;
        const stepId = requireWizardStepId(this.#host.view.state.steps, this.#host.view.state.stepIndex);
        const ui = this.#host.view.requireUi();
        this.#host.view.updateProgress(ui);
        this.#host.view.syncNavigation(ui, stepId);
        if (stepId === 'product_access' && status.entitlement !== null) {
            await this.#showStep(this.#host.view.state.steps.indexOf('account'));
        } else if (stepId === 'product_access') {
            const authoritativeFlowChanged = status.selectedProductAccessFlow !== priorAuthoritativeFlow;
            const selectionWasAuthoritative = priorProductAccessFlow === null || priorProductAccessFlow === priorAuthoritativeFlow;
            const shouldSynchronizeSelection = status.selectedProductAccessFlow !== null && status.selectedProductAccessFlow !== priorProductAccessFlow && (authoritativeFlowChanged || selectionWasAuthoritative);
            if (authoritativeFlowChanged || shouldSynchronizeSelection) this.clearProductKey();
            if (shouldSynchronizeSelection) {
                this.#host.view.syncProductAccessSelection(ui, status.selectedProductAccessFlow, false);
            }
            this.#syncOperationBanner(status);
        }
    }

    async #resynchronizeAfterMutationFailure(revision: number): Promise<void> {
        const current = await this.#host.data.refreshStatus();
        if (revision !== this.#revision) return;
        if (current === null) throw new Error('Wizard licensing status resynchronization was superseded');
        this.#host.data.applyStatus(current);
        if (requireWizardStepId(this.#host.view.state.steps, this.#host.view.state.stepIndex) === 'product_access') this.#syncOperationBanner(current);
    }

    clearProductKey(): void {
        const input = optionalInput(dom.resolve('#wizard-product-key', this.#host.view.requireUi().content), 'Wizard product key input');
        if (input) input.value = '';
    }

    clearInlineError(): void {
        this.#host.view.state.inlineError = null;
        this.#syncInlineError();
    }

    async #activate(source: HTMLElement): Promise<void> {
        const input = optionalInput(dom.resolve('#wizard-product-key', this.#host.view.requireUi().content), 'Wizard product key input');
        const status = this.#requireStatus();
        const flow = status.edition === 'soai-os' && status.declaration === 'personal' ? 'personal_os_activation' : 'commercial_activation';
        const documents = this.#host.view.state.legalDocumentSets.get(flow);
        const acceptance = optionalInput(dom.resolve('#wizard-activation-acceptance', this.#host.view.requireUi().content), 'Wizard activation acceptance');
        const environmentElement = dom.resolve('#wizard-online-deployment-environment', this.#host.view.requireUi().content);
        const environment = environmentElement instanceof HTMLSelectElement && (environmentElement.value === 'production' || environmentElement.value === 'non_production') ? environmentElement.value : null;
        if (documents === undefined) throw new TypeError(`Wizard activation governing documents are unavailable for ${flow}`);
        if (input === null || input.value.trim().length < 16 || acceptance?.checked !== true) return;
        if (status.declaration === 'organization_commercial' && environment === null) throw new TypeError('Wizard commercial activation deployment environment is unavailable');
        let productKey = input.value;
        input.value = '';
        if (
            await this.#withLoading(source, () =>
                this.mutate((currentStatus) => {
                    try {
                        return this.#host.data.activateCredential(currentStatus, { activationCredential: productKey, deploymentEnvironment: environment, legalAcceptances: licensingLegalAcceptances(documents) });
                    } finally {
                        productKey = '';
                    }
                })
            )
        )
            await this.#showAccountIfEntitled();
    }

    async #activateEvaluation(source: HTMLElement): Promise<void> {
        const status = this.#requireStatus();
        const documents = this.#host.view.state.legalDocumentSets.get('core_evaluation');
        if (documents === undefined) throw new TypeError('Wizard evaluation governing documents are unavailable');
        const pendingEvaluation = status.pendingEvaluation;
        if (pendingEvaluation === null) return;
        if (await this.#withLoading(source, () => this.mutate((currentStatus) => this.#host.data.activateEvaluation(currentStatus, pendingEvaluation.evaluationId, licensingLegalAcceptances(documents))))) await this.#showAccountIfEntitled();
    }

    async #reconcile(source: HTMLElement): Promise<void> {
        if (await this.#withLoading(source, () => this.mutate((status) => this.#host.data.reconcile(status)))) await this.#showAccountIfEntitled();
    }

    async #exportOffline(source: HTMLElement): Promise<void> {
        const status = this.#requireStatus();
        const environmentElement = dom.resolve('#wizard-offline-deployment-environment', this.#host.view.requireUi().content);
        const environment = environmentElement instanceof HTMLSelectElement && (environmentElement.value === 'production' || environmentElement.value === 'non_production') ? environmentElement.value : null;
        if (status.declaration === 'organization_commercial' && environment === null) throw new TypeError('Wizard offline activation deployment environment is unavailable');
        await this.#withLoading(source, () => this.mutate((currentStatus) => this.#host.data.exportOffline(currentStatus, environment)));
    }

    async #startEvaluation(source: HTMLElement): Promise<void> {
        const documents = this.#host.view.state.legalDocumentSets.get('core_evaluation');
        const form = dom.resolve('#wizard-organization-form', this.#host.view.requireUi().content);
        if (documents === undefined) throw new TypeError('Wizard evaluation governing documents are unavailable');
        if (!this.#host.view.state.evaluationAcknowledged) return;
        if (!(form instanceof HTMLFormElement)) throw new TypeError('Wizard organization form is unavailable');
        const organization = readWizardOrganization(form);
        await this.#withLoading(source, () => this.mutate((status) => this.#host.data.startEvaluation(status, organization, licensingLegalAcceptances(documents))));
    }

    async #importOffline(file: File): Promise<void> {
        if (await this.mutate((status) => this.#host.data.importOffline(status, file))) await this.#showAccountIfEntitled();
    }

    #openOfflineChooser(): void {
        optionalInput(dom.resolve('#wizard-offline-certificate', this.#host.view.requireUi().content), 'Wizard offline certificate input')?.click();
    }

    async #showAccountIfEntitled(): Promise<void> {
        if (this.#host.view.state.status?.entitlement) await this.#showStep(this.#host.view.state.steps.indexOf('account'));
    }

    async #withLoading<T>(source: HTMLElement, operation: () => Promise<T>): Promise<T> {
        if (!(source instanceof HTMLButtonElement)) return operation();
        beginLoadingButton(source);
        try {
            return await operation();
        } finally {
            clearLoadingButtonIfNeeded(source);
        }
    }

    #requireStatus(): WizardStatusResponse {
        const status = this.#host.view.state.status;
        if (status === null) throw new Error('WizardPage: authoritative licensing status is unavailable');
        return status;
    }

    #syncNavigation(): void {
        this.#host.view.syncNavigation(this.#host.view.requireUi(), requireWizardStepId(this.#host.view.state.steps, this.#host.view.state.stepIndex));
    }

    #syncInlineError(): void {
        const message = this.#host.view.state.inlineError ?? '';
        for (const element of dom.resolveAll('[data-wizard-licensing-error]', this.#host.view.requireUi().content)) {
            const error = optionalHTMLElement(element, 'Wizard licensing error');
            if (error === null) continue;
            this.#host.view.updateText(error, message);
            this.#host.view.toggleHidden(error, message.length === 0);
        }
    }

    #syncControls(): void {
        const content = this.#host.view.requireUi().content;
        const operation = this.#host.view.state.status?.operation ?? null;
        const operationInProgress = operation !== null && isLicensingOperationInProgress(operation.state);
        for (const control of dom.resolveAll('[data-licensing-mutation], #wizard-offline-certificate', content)) {
            if (!(control instanceof HTMLButtonElement || control instanceof HTMLInputElement)) continue;
            const action = control instanceof HTMLButtonElement ? control.dataset['action'] : null;
            if (this.#host.view.state.isBusy) control.disabled = true;
            else if (operationInProgress && action !== 'wizard-reconcile') control.disabled = true;
            else control.disabled = false;
            control.toggleAttribute('aria-disabled', control.disabled);
        }
    }

    #syncOperationBanner(status: WizardStatusResponse): void {
        const statusElement = optionalHTMLElement(dom.resolve('[data-wizard-operation-status]', this.#host.view.requireUi().content), 'Wizard operation status');
        if (statusElement === null) return;
        const banner = statusElement.closest('.wizard-operation-banner');
        if (!(banner instanceof HTMLElement)) throw new TypeError('Wizard operation banner is unavailable');
        const operationState = status.operation === null ? null : presentLicensingOperationState(status.operation.state);
        this.#host.view.updateText(statusElement, operationState ?? '');
        this.#host.view.toggleHidden(banner, operationState === null);
        const warning = optionalHTMLElement(dom.resolve('[data-wizard-operation-warning]', banner), 'Wizard operation switch warning');
        if (warning !== null) this.#host.view.toggleHidden(warning, status.operation === null || !isLicensingOperationInProgress(status.operation.state));
    }
}

export { WizardLicensingActionController };
