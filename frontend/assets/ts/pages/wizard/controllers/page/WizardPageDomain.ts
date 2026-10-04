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
import { buildAiSetupHandoffRoute, isAiSetupResumeRequest } from '@core/routing/router/aiSetupRoutes.ts';
import { AUTH_ROUTE_LOGIN } from '@core/routing/router/authRouteTarget.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageHost } from '@core/routing/pages/basepagecore/PageHost.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageStreamingContract } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { isFunction } from '@core/typeGuards.ts';
import { createInitialWizardState, type WizardState } from '@features/wizard/public.ts';
import { isWizardActionId } from '@pages/wizard/actions.ts';
import { deriveAiSetupStepIds, isAiSetupWizardStepId, requireWizardStepId, syncWizardSteps } from '@pages/wizard/contracts/constants.ts';
import { ensureWizardStatusSnapshot, markWizardFirstRunModalsPending, markWizardHasUsers, persistWizardState, shouldResumeAtCompletionStep, shouldShowWizard, submitWizardAccount } from '@pages/wizard/controllers/page/effects.ts';
import { wireWizardRootEvents } from '@pages/wizard/controllers/page/events.ts';
import { WizardLicensingRequestsController } from '@pages/wizard/controllers/page/WizardLicensingRequestsController.ts';
import { WizardPageEffectState } from '@pages/wizard/controllers/page/WizardPageEffectState.ts';
import { WizardPageUiController } from '@pages/wizard/controllers/wizardUiController.ts';
import { WizardPageService } from '@pages/wizard/services/service.ts';
import { AiSetupFlowController } from '@pages/wizard/services/aisetup/AiSetupFlowController.ts';
import type { WizardCompletionDestination } from '@pages/wizard/services/contracts.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { renderWizardShellView, renderWizardSuppressedView } from '@pages/wizard/view.ts';
import { getApiClient } from '@core/api/service.ts';
import { downloadAuthenticatedResponse } from '@core/api/authenticatedDownload.ts';
import { createAbortError } from '@core/errors/abort.ts';
import { i18n } from '@core/i18n/index.ts';

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
    streaming: PageStreamingContract;
}

class WizardPageDomain {
    readonly state: WizardState;
    readonly #dependencies: WizardPageDomainDependencies;
    readonly #effects: WizardPageEffectState;
    readonly #ui: WizardPageUiController;
    readonly #aiSetup: AiSetupFlowController;
    readonly #service: WizardPageService;
    readonly #licensing: WizardLicensingRequestsController;

    constructor(dependencies: WizardPageDomainDependencies) {
        this.#dependencies = dependencies;
        this.state = createInitialWizardState();
        this.state.totalSteps = this.state.steps.length;
        this.#effects = new WizardPageEffectState(dependencies.auth, dependencies.storage, (message, error) => wizardLogger('warn', message, error));
        this.#aiSetup = this.#createAiSetup();
        this.#ui = this.#createUi();
        this.#licensing = new WizardLicensingRequestsController({
            licenseService: dependencies.licenseService,
            onPolledStatus: (status) => void this.#service.applyObservedStatus(status).catch((error) => wizardLogger('error', 'WizardPage: apply polled licensing status', error)),
            onPollFailure: () => this.#dependencies.feedback.show(i18n.t('wizard.productAccess.pollUnavailable'), 'warning')
        });
        this.#service = this.#createService();
    }

    async loadStatus(): Promise<void> {
        const status = await ensureWizardStatusSnapshot(this.#effects);
        if (status !== null) this.#applyStatus(status);
    }

    async resolveVisibility(parameters: JsonObject): Promise<void> {
        const resume = isAiSetupResumeRequest(parameters) && this.#dependencies.auth.isAuthenticated && !this.#dependencies.storage.isWizardCompletionPending() && this.#dependencies.storage.isAiSetupResumable();
        this.state.isAiSetupResume = resume;
        if (resume) {
            this.#effects.visible = true;
            syncWizardSteps(this.state);
            return;
        }
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
        await this.#service.showStep(this.#startIndex(), { showNextLoading: false, focusHeading: this.state.isAiSetupResume });
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
                },
                keydown: {
                    preventDefault: 'never',
                    onAction: ({ event, action, actionElement }): void => {
                        if (!(event instanceof KeyboardEvent) || (event.key !== 'Enter' && event.key !== ' ') || actionElement.getAttribute('role') !== 'button') return;
                        event.preventDefault();
                        this.#service.executeAction(action, actionElement);
                    }
                }
            }
        });
    }

    destroy(): void {
        this.#service.destroy();
        this.#licensing.destroy();
        this.#dependencies.pageLifecycle.abortListeners('wizard-destroy');
        this.#ui.reset();
        this.#effects.visible = null;
        this.#effects.status = null;
    }

    #createAiSetup(): AiSetupFlowController {
        return new AiSetupFlowController({
            streaming: this.#dependencies.streaming,
            storage: this.#dependencies.storage,
            view: {
                createViewContext: () => this.#ui.createViewContext(),
                updateHTML: (element, value) => this.#dependencies.pageDom.updateHtml(element, value),
                updateText: (element, value) => this.#dependencies.pageDom.updateText(element, value),
                toggleHidden: (element, hidden) => this.#dependencies.pageElements.toggleHidden(element, hidden),
                toggleClassName: (element, className, value) => this.#dependencies.pageDom.toggleClass(element, className, value),
                updateProperty: (element, property, value) => this.#dependencies.pageDom.updateProperty(element, property, value)
            },
            requireContent: () => this.#ui.ensureUi().content,
            syncSteps: () => this.#syncAiSetupSteps(),
            syncNavigation: () => this.#syncCurrentNavigation(),
            goToStep: (stepId) => void this.#service.aiNavigator.showStep(stepId).catch((error) => wizardLogger('error', 'WizardPage: AI setup navigation failed', error)),
            notify: (message, type) => this.#dependencies.feedback.show(message, type)
        });
    }

    #syncAiSetupSteps(): void {
        this.state.aiSetupSteps = deriveAiSetupStepIds(this.#aiSetup.controller.needsConnectStep());
        syncWizardSteps(this.state);
        if (this.#isDomUsable()) this.#ui.updateProgress(this.#ui.ensureUi());
    }

    #isDomUsable(): boolean {
        return this.#dependencies.pageHost.getContext() !== null && !this.#dependencies.pageLifecycle.isDestroyed;
    }

    #syncCurrentNavigation(): void {
        if (this.#isDomUsable()) this.#ui.syncNavigation(this.#ui.ensureUi(), requireWizardStepId(this.state.steps, this.state.stepIndex));
    }

    #createUi(): WizardPageUiController {
        return new WizardPageUiController({
            state: this.state,
            aiSetup: { canContinue: (stepId) => this.#aiSetup.canContinue(stepId), nextLabel: (stepId) => this.#aiSetup.nextLabel(stepId), hasReadyModel: () => this.#aiSetup.hasReadyModel() },
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
                isDomUsable: () => this.#isDomUsable(),
                createViewContext: () => this.#ui.createViewContext(),
                updateProgress: (ui) => this.#ui.updateProgress(ui),
                syncWelcomeLanguageFlag: (content) => this.#ui.syncWelcomeLanguageFlag(content),
                syncNavigation: (ui, stepId) => this.#ui.syncNavigation(ui, stepId),
                syncCurrentNavigation: () => this.#syncCurrentNavigation(),
                syncUseSelection: (ui) => this.#ui.syncUseSelection(ui),
                syncAccountError: (account, message) => this.#ui.syncAccountError(account, message),
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
                fetchLicenseText: () => this.#licensing.fetchLicenseText(),
                acceptLicense: (status) => this.#licensing.mutateStatus((signal) => getApiClient().webui.wizard.acceptLicense(status.draftRevision, status.licenseFingerprint, { signal })),
                declareUse: (status, declaration, confirmed) => this.#licensing.mutateStatus((signal) => getApiClient().webui.wizard.declareUse(status.draftRevision, declaration, { confirmed, revision: declaration === 'personal' ? status.personalAttestationRevision : null }, { signal })),
                evaluationTerms: () => this.#licensing.evaluationTerms(),
                personalPurchaseTerms: () => this.#licensing.personalPurchaseTerms(),
                governingDocuments: (flow) => this.#licensing.governingDocuments(flow),
                startEvaluation: (status, organization, legalAcceptances) => this.#licensing.mutateStatus((signal) => getApiClient().webui.wizard.startEvaluation(status.draftRevision, organization, legalAcceptances, { signal })),
                activateCredential: (status, input) => this.#licensing.mutateStatus((signal) => getApiClient().webui.wizard.activateCredential(status.draftRevision, input, { signal })),
                activateEvaluation: (status, pendingEvaluationId, legalAcceptances) => this.#licensing.mutateStatus((signal) => getApiClient().webui.wizard.activateEvaluation(status.draftRevision, pendingEvaluationId, legalAcceptances, { signal })),
                reconcile: (status) => this.#licensing.mutateStatus((signal) => getApiClient().webui.wizard.reconcileOperation(status.draftRevision, { signal })),
                exportOffline: async (status, environment) => {
                    this.#licensing.invalidateStatusObservation();
                    const response = await this.#licensing.runLicensingRequest((signal) => getApiClient().webui.wizard.exportOfflineRequest(status.draftRevision, environment, { signal }));
                    await downloadAuthenticatedResponse(response);
                    const refreshed = await this.#licensing.refreshStatus();
                    if (refreshed === null) throw createAbortError('Wizard licensing status refresh superseded');
                    return refreshed;
                },
                importOffline: (status, file) => this.#licensing.mutateStatus((signal) => getApiClient().webui.wizard.importOfflineCertificate(status.draftRevision, file, { signal })),
                refreshStatus: () => this.#licensing.refreshStatus(),
                applyStatus: (status) => this.#applyStatus(status),
                invalidateLicensingRequests: () => this.#licensing.invalidateLicensingRequests()
            },
            aiSetup: this.#aiSetup,
            completion: {
                dispatchWizardCompleted: () => dispatchCustomEvent('soai:wizard:completed', {}),
                navigateAfterCompletion: (isSessionActivationRequired, destination) => this.#navigateAfterCompletion(isSessionActivationRequired, destination),
                refreshLogos: () => getBranding().updateAllLogos(),
                logWarn: (operation, error) => wizardLogger('warn', `WizardPage: ${operation}`, error),
                logError: (operation, error) => wizardLogger('error', `WizardPage: ${operation}`, error),
                notify: (message, type) => this.#dependencies.feedback.show(message, type)
            }
        });
    }

    #applyStatus(status: NonNullable<WizardState['status']>): void {
        this.state.status = status;
        this.state.completedSummary = status.completedSummary;
        this.state.declarationSelection = status.declaration;
        this.state.attestationConfirmed = status.personalAttestationConfirmedAtMs !== null;
        this.state.evaluationAcknowledged = status.evaluationAcknowledgedAtMs !== null;
        this.state.requiresProductAccess = status.declaration !== null && !(status.edition === 'soai-core' && status.declaration === 'personal');
        syncWizardSteps(this.state);
        this.#licensing.observeStatus(status);
    }

    #startIndex(): number {
        const setup = this.#dependencies.storage.getAiSetup();
        const storedStep = setup !== null && (this.state.isAiSetupResume || setup.disposition === 'in_progress') && isAiSetupWizardStepId(setup.step) ? this.state.steps.indexOf(setup.step) : -1;
        if (this.state.isAiSetupResume) return Math.max(0, storedStep);
        if (!shouldResumeAtCompletionStep(this.#effects)) return this.#resumeIndex();
        return storedStep >= 0 ? storedStep : this.state.steps.length - 1;
    }

    #resumeIndex(): number {
        const status = this.state.status;
        if (status === null || (status.draftRevision === 0 && status.licenseAcceptedAtMs === null)) return 0;
        const index = this.state.steps.indexOf(status.resumeStep);
        return index < 0 ? 0 : index;
    }

    async #navigateAfterCompletion(isSessionActivationRequired: boolean, destination: WizardCompletionDestination): Promise<void> {
        if (!isFunction(this.#dependencies.router.navigate)) throw new Error('WizardPage requires router.navigate for completion');
        if (isSessionActivationRequired) {
            await this.#dependencies.router.navigate(AUTH_ROUTE_LOGIN);
            return;
        }
        await this.#dependencies.router.navigate(destination === 'chat' ? buildAiSetupHandoffRoute() : this.#dependencies.router.getDefaultRoute());
    }
}

export { WizardPageDomain };
export type { WizardPageDomainDependencies };
