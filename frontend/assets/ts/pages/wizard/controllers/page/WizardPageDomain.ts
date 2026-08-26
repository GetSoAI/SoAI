/* SoAI - Wizard page state, workflow, presentation, and lifecycle ownership [frontend/assets/ts/pages/wizard/controllers/page/WizardPageDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AuthManager } from '@core/auth/public.ts';
import { getBranding } from '@core/branding/public.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { dispatchCustomEvent } from '@core/environment/public.ts';
import type { LanguageService } from '@core/routing/pages/pagetypes/public.ts';
import type { LicenseServiceInterface } from '@core/licenseservice/types.ts';
import type { PageContext } from '@core/pagecontext/public.ts';
import type { Router } from '@core/routing/router/Router.ts';
import { AUTH_ROUTE_LOGIN } from '@core/routing/router/authRouteTarget.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageHost } from '@core/routing/pages/basepagecore/PageHost.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { isFunction } from '@core/typeGuards.ts';
import { createInitialWizardState, type WizardState } from '@features/wizard/public.ts';
import { isWizardActionId } from '@pages/wizard/actions.ts';
import { deriveWizardStepIds, WIZARD_STEP_IDS } from '@pages/wizard/contracts/constants.ts';
import { ensureWizardStatusSnapshot, markWizardFirstRunModalsPending, markWizardHasUsers, persistWizardState, shouldResumeAtCompletionStep, shouldShowWizard, submitWizardAccount } from '@pages/wizard/controllers/page/effects.ts';
import { wireWizardRootEvents } from '@pages/wizard/controllers/page/events.ts';
import { WizardPageEffectState } from '@pages/wizard/controllers/page/WizardPageEffectState.ts';
import { WizardPageUiController } from '@pages/wizard/controllers/wizardUiController.ts';
import { WizardPageService } from '@pages/wizard/services/service.ts';
import { renderWizardShellView, renderWizardSuppressedView } from '@pages/wizard/view.ts';
import { getApiClient } from '@core/api/service.ts';
import { downloadAuthenticatedResponse } from '@core/api/authenticatedDownload.ts';
import { AsyncOnceGuard } from '@core/concurrency/AsyncOnce.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { createAbortError, runWithAbortSignalScope } from '@core/errors/abort.ts';
import { i18n } from '@core/i18n/index.ts';
import type { WizardLicensingDocumentResponse } from '@core/api/contracts/wizardLicensingMutations.ts';
import { isDetailedWizardStatus, type WizardStatusResponse } from '@core/api/contracts/wizardLicensingContracts.ts';
import { LicensingOperationPollController } from '@core/licensing/operationPollController.ts';
import type { LicensingLegalDocumentSet, LicensingLegalFlow } from '@core/api/contracts/licensingLegalDocumentContracts.ts';

const wizardLogger = createModuleLogger('WizardPage', { defaultLevel: 'warn' });

interface WizardPageDomainDependencies {
    auth: AuthManager;
    feedback: PageFeedback;
    languageService: LanguageService;
    licenseService: LicenseServiceInterface;
    pageContext: PageContext;
    pageDom: PageDom;
    pageElements: PageUi;
    pageHost: PageHost;
    pageLifecycle: PageLifecycle;
    router: Router;
    services: PageServices;
    storage: StorageService;
}

class WizardPageDomain {
    readonly state: WizardState;
    readonly #dependencies: WizardPageDomainDependencies;
    readonly #effects: WizardPageEffectState;
    readonly #ui: WizardPageUiController;
    readonly #service: WizardPageService;
    readonly #licenseLoad = new AsyncOnceGuard<string>();
    readonly #evaluationTermsLoad = new AsyncOnceGuard<WizardLicensingDocumentResponse>();
    readonly #purchaseTermsLoad = new AsyncOnceGuard<WizardLicensingDocumentResponse>();
    readonly #governingDocumentLoads = new Map<LicensingLegalFlow, AsyncOnceGuard<LicensingLegalDocumentSet>>();
    readonly #statusRequests = new LatestRequestController();
    readonly #licensingRequests = new LatestRequestController();
    readonly #licensingPoll: LicensingOperationPollController<WizardStatusResponse>;
    #pollFailureNotified = false;

    constructor(dependencies: WizardPageDomainDependencies) {
        this.#dependencies = dependencies;
        this.state = createInitialWizardState();
        this.state.totalSteps = WIZARD_STEP_IDS.length;
        this.#effects = new WizardPageEffectState(dependencies.auth, dependencies.storage, (message, error) => wizardLogger('warn', message, error));
        this.#ui = this.#createUi();
        this.#service = this.#createService();
        this.#licensingPoll = new LicensingOperationPollController({
            fetchStatus: (signal) => this.#refreshStatusRequired(signal),
            onStatus: (status) => {
                this.#pollFailureNotified = false;
                void this.#service.applyObservedStatus(status).catch((error) => wizardLogger('error', 'WizardPage: apply polled licensing status', error));
            },
            onFailure: () => {
                if (this.#pollFailureNotified) return;
                this.#pollFailureNotified = true;
                this.#dependencies.feedback.show(i18n.t('wizard.productAccess.pollUnavailable'), 'warning');
            }
        });
    }

    async loadStatus(): Promise<void> {
        const status = await ensureWizardStatusSnapshot(this.#effects);
        if (status !== null) this.#applyStatus(status);
    }

    async resolveVisibility(): Promise<void> {
        await shouldShowWizard(this.#effects);
    }

    render(): string {
        const context = this.#ui.createViewContext();
        return this.#effects.visible === false ? renderWizardSuppressedView(context) : renderWizardShellView(context);
    }

    async initialize(): Promise<void> {
        if (this.#effects.visible === false) return;
        const ui = this.#ui.ensureUi();
        getBranding().updateLogoElement(ui.logo, 'ui');
        const startIndex = shouldResumeAtCompletionStep(this.#effects) ? this.state.steps.length - 1 : this.#resumeIndex();
        await this.#service.showStep(startIndex);
    }

    bindPageEvents(): void {
        if (this.#effects.visible === false) return;
        const ui = this.#ui.ensureUi();
        const signal = this.#dependencies.pageLifecycle.beginListeners();
        wireWizardRootEvents({
            root: ui.root,
            signal,
            service: this.#service,
            state: this.state,
            languageService: this.#dependencies.languageService,
            logError: (operation, error) => wizardLogger('error', `WizardPage: ${operation}`, error)
        });
        bindPageActionDispatcher({
            root: ui.root,
            signal,
            label: 'WizardPage',
            isAction: isWizardActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'always',
                    onAction: ({ action, actionElement }): void => this.#service.executeAction(action, actionElement)
                }
            }
        });
    }

    destroy(): void {
        this.#service.destroy();
        this.#licenseLoad.dispose();
        this.#evaluationTermsLoad.dispose();
        this.#purchaseTermsLoad.dispose();
        for (const load of this.#governingDocumentLoads.values()) load.dispose();
        this.#governingDocumentLoads.clear();
        this.#statusRequests.invalidate();
        this.#licensingRequests.invalidate();
        this.#licensingPoll.destroy();
        this.#dependencies.pageLifecycle.abortListeners('wizard-destroy');
        this.#ui.reset();
        this.#effects.visible = null;
        this.#effects.status = null;
    }

    #createUi(): WizardPageUiController {
        return new WizardPageUiController({
            state: this.state,
            languageService: this.#dependencies.languageService,
            getIconSync: (name, options) => this.#dependencies.services.getIconSync(name, options),
            sanitizer: this.#dependencies.pageContext.sanitizer,
            requireHTMLElement: (selector, context) => this.#dependencies.pageDom.requireHTMLElement(selector, context instanceof Element ? context : undefined),
            updateStyle: (element, property, value) => this.#dependencies.pageDom.updateStyle(element, property, value),
            toggleClassName: (element, className, value) => this.#dependencies.pageDom.toggleClass(element, className, value),
            updateText: (element, value) => this.#dependencies.pageDom.updateText(element, value),
            toggleHidden: (element, hidden) => this.#dependencies.pageElements.toggleHidden(element, hidden),
            updateProperty: (element, property, value) => this.#dependencies.pageDom.updateProperty(element, property, value),
            updateAttribute: (element, attribute, value) => this.#dependencies.pageDom.updateAttribute(element, attribute, value)
        });
    }

    #createService(): WizardPageService {
        return new WizardPageService({
            view: {
                state: this.state,
                requireUi: () => this.#ui.ensureUi(),
                requireAccountUi: () => this.#ui.requireAccountUi(),
                isDomUsable: () => this.#dependencies.pageHost.getContext() !== null && !this.#dependencies.pageLifecycle.isDestroyed,
                createViewContext: () => this.#ui.createViewContext(),
                updateProgress: (ui) => this.#ui.updateProgress(ui),
                syncNavigation: (ui, stepId) => this.#ui.syncNavigation(ui, stepId),
                syncUseSelection: (ui) => this.#ui.syncUseSelection(ui),
                selectedProductAccessFlow: (ui) => this.#ui.selectedProductAccessFlow(ui),
                syncProductAccessSelection: (ui, selected, focusPanel) => this.#ui.syncProductAccessSelection(ui, selected, focusPanel),
                updateText: (element, value) => this.#dependencies.pageDom.updateText(element, value),
                toggleHidden: (element, hidden) => this.#dependencies.pageElements.toggleHidden(element, hidden),
                updateHTML: (element, value) => this.#dependencies.pageDom.updateHtml(element, value)
            },
            data: {
                submitWizardAccount: (username, password) => submitWizardAccount(this.#effects, username, password),
                markWizardHasUsers: () => markWizardHasUsers(this.#effects),
                persistWizardState: () => persistWizardState(this.#effects),
                markWizardFirstRunModalsPending: () => markWizardFirstRunModalsPending(this.#effects),
                fetchLicenseText: () => this.#fetchLicenseText(),
                acceptLicense: (status) => this.#mutateStatus((signal) => getApiClient().webui.wizard.acceptLicense(status.draftRevision, status.licenseFingerprint, { signal })),
                declareUse: (status, declaration, confirmed) => this.#mutateStatus((signal) => getApiClient().webui.wizard.declareUse(status.draftRevision, declaration, { confirmed, revision: declaration === 'personal' ? status.personalAttestationRevision : null }, { signal })),
                evaluationTerms: () => this.#evaluationTermsLoad.run(() => getApiClient().webui.wizard.evaluationTerms()),
                personalPurchaseTerms: () => this.#purchaseTermsLoad.run(() => getApiClient().webui.wizard.personalPurchaseTerms()),
                governingDocuments: (flow) => this.#governingDocuments(flow),
                startEvaluation: (status, organization, legalAcceptances) => this.#mutateStatus((signal) => getApiClient().webui.wizard.startEvaluation(status.draftRevision, organization, legalAcceptances, { signal })),
                activateCredential: (status, input) => this.#mutateStatus((signal) => getApiClient().webui.wizard.activateCredential(status.draftRevision, input, { signal })),
                activateEvaluation: (status, pendingEvaluationId, legalAcceptances) => this.#mutateStatus((signal) => getApiClient().webui.wizard.activateEvaluation(status.draftRevision, pendingEvaluationId, legalAcceptances, { signal })),
                reconcile: (status) => this.#mutateStatus((signal) => getApiClient().webui.wizard.reconcileOperation(status.draftRevision, { signal })),
                exportOffline: async (status, environment) => {
                    this.#invalidateStatusObservation();
                    const response = await this.#runLicensingRequest((signal) => getApiClient().webui.wizard.exportOfflineRequest(status.draftRevision, environment, { signal }));
                    await downloadAuthenticatedResponse(response);
                    const refreshed = await this.#refreshStatus();
                    if (refreshed === null) throw createAbortError('Wizard licensing status refresh superseded');
                    return refreshed;
                },
                importOffline: (status, file) => this.#mutateStatus((signal) => getApiClient().webui.wizard.importOfflineCertificate(status.draftRevision, file, { signal })),
                refreshStatus: () => this.#refreshStatus(),
                applyStatus: (status) => this.#applyStatus(status),
                invalidateLicensingRequests: () => this.#licensingRequests.invalidate()
            },
            completion: {
                dispatchWizardCompleted: () => dispatchCustomEvent('soai:wizard:completed', {}),
                navigateAfterCompletion: (isSessionActivationRequired) => this.#navigateAfterCompletion(isSessionActivationRequired),
                refreshLogos: () => getBranding().updateAllLogos(),
                logWarn: (operation, error) => wizardLogger('warn', `WizardPage: ${operation}`, error),
                logError: (operation, error) => wizardLogger('error', `WizardPage: ${operation}`, error),
                notify: (message, type) => this.#dependencies.feedback.show(message, type)
            }
        });
    }

    async #fetchLicenseText(): Promise<string> {
        return this.#licenseLoad.run(async () => {
            const data = await this.#dependencies.licenseService.fetchLicenseData();
            if (typeof data.licenseText !== 'string' || !data.licenseText.trim()) throw new Error('WizardPage: license text is unavailable');
            return data.licenseText;
        });
    }

    #governingDocuments(flow: LicensingLegalFlow): Promise<LicensingLegalDocumentSet> {
        let load = this.#governingDocumentLoads.get(flow);
        if (load === undefined) {
            load = new AsyncOnceGuard<LicensingLegalDocumentSet>();
            this.#governingDocumentLoads.set(flow, load);
        }
        return load.run(() => getApiClient().webui.wizard.governingDocuments(flow));
    }

    #applyStatus(status: NonNullable<WizardState['status']>): void {
        this.state.status = status;
        this.state.completedSummary = status.completedSummary;
        this.state.declarationSelection = status.declaration;
        this.state.attestationConfirmed = status.personalAttestationConfirmedAtMs !== null;
        this.state.evaluationAcknowledged = status.evaluationAcknowledgedAtMs !== null;
        const requiresProductAccess = status.declaration !== null && !(status.edition === 'soai-core' && status.declaration === 'personal');
        this.state.steps = deriveWizardStepIds(requiresProductAccess);
        this.state.totalSteps = this.state.steps.length;
        this.#licensingPoll.update(status);
    }

    #invalidateStatusObservation(): void {
        this.#licensingPoll.pause();
        this.#statusRequests.invalidate();
    }

    async #mutateStatus(operation: (signal: AbortSignal) => Promise<WizardStatusResponse>): Promise<WizardStatusResponse> {
        this.#invalidateStatusObservation();
        return this.#runLicensingRequest(operation);
    }

    async #runLicensingRequest<T>(operation: (signal: AbortSignal) => Promise<T>): Promise<T> {
        const result = await this.#licensingRequests.runLatest((run) => operation(run.signal));
        if (result === null) throw createAbortError('Wizard licensing request superseded');
        return result;
    }

    async #refreshStatus(signal?: AbortSignal): Promise<WizardStatusResponse | null> {
        return this.#statusRequests.runLatest(async (run) =>
            runWithAbortSignalScope([run.signal, signal], async (combinedSignal) => {
                const status = await getApiClient().webui.wizard.status({ signal: combinedSignal });
                if (!isDetailedWizardStatus(status)) throw new Error('Wizard licensing details require an active setup ceremony');
                return status;
            })
        );
    }

    async #refreshStatusRequired(signal: AbortSignal): Promise<WizardStatusResponse> {
        const status = await this.#refreshStatus(signal);
        if (status === null) throw createAbortError('Wizard licensing status refresh superseded');
        return status;
    }

    #resumeIndex(): number {
        const status = this.state.status;
        if (status === null || (status.draftRevision === 0 && status.licenseAcceptedAtMs === null)) return 0;
        const index = this.state.steps.indexOf(status.resumeStep);
        return index < 0 ? 0 : index;
    }

    async #navigateAfterCompletion(isSessionActivationRequired: boolean): Promise<void> {
        if (!isFunction(this.#dependencies.router.navigate)) throw new Error('WizardPage requires router.navigate for completion');
        await this.#dependencies.router.navigate(isSessionActivationRequired ? AUTH_ROUTE_LOGIN : 'dashboard');
    }
}

export { WizardPageDomain };
export type { WizardPageDomainDependencies };
