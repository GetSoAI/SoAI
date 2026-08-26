/* SoAI - Model detail session, presentation, workflow, and lifecycle ownership [frontend/assets/ts/pages/modeldetail/controllers/page/ModelDetailPageDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { PageContext } from '@core/pagecontext/public.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageCollapsibleCards } from '@core/routing/pages/basepagelayout/PageCollapsibleCards.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { StatusManager } from '@core/state/public.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { isString } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { ApiClient } from '@core/api/service.ts';
import { requireCatalogStore } from '@features/catalog/public.ts';
import { MODEL_DETAIL_TEST_MODAL_ID } from '@features/modeldetail/public.ts';
import { MODELS_RENAME_MODEL_MODAL_ID } from '@features/models/public.ts';
import { applyModelDetailTabChange, setupModelDetailHeaderButtons } from '@pages/modeldetail/controllers/page/dom.ts';
import { loadModelDetailData } from '@pages/modeldetail/controllers/page/effects/service.ts';
import { ModelDetailEventController } from '@pages/modeldetail/controllers/page/ModelDetailEventController.ts';
import { cleanupModelDetailPage, ensureModelDetailUi, handleModelDetailSwitchToParametersAction, loadModelDetailDataAndPendingAction, setupModelDetailPage } from '@pages/modeldetail/controllers/page/guards.ts';
import { composeModelDetailDomains } from '@pages/modeldetail/controllers/page/modelDetailDomainComposition.ts';
import { composeModelDetailRuntime } from '@pages/modeldetail/controllers/page/modelDetailRuntimeComposition.ts';
import { resetModelDetailPageBeforeInitialize } from '@pages/modeldetail/controllers/page/runtime.ts';
import { requireModelDetailUi, type ModelDetailUi } from '@pages/modeldetail/dom.ts';
import { loadModelDetailIcons } from '@pages/modeldetail/rendering/modelDetailIcons.ts';
import { ModelDetailCapabilityState } from '@pages/modeldetail/state/ModelDetailCapabilityState.ts';
import { ChangeNotificationSource } from '@core/primitives/changeNotificationSource.ts';
import type { ModelDetailSaveStatusState } from '@pages/modeldetail/state/ModelDetailSaveStatusState.ts';
import { ModelDetailSession } from '@pages/modeldetail/state/ModelDetailSession.ts';

interface ModelDetailPageDomainOwners {
    api: ApiClient;
    collapsibleCards: PageCollapsibleCards;
    dom: typeof import('@core/dom/dom.ts').dom;
    feedback: PageFeedback;
    layout: PageLayout;
    modalPresenter: ModalPresenterApi;
    pageContext: PageContext;
    pageDom: PageDom;
    pageElements: PageUi;
    pageLifecycle: PageLifecycle;
    pageResources: PageResources;
    router: Router;
    services: PageServices;
    statusManager: StatusManager;
    storage: StorageService;
    streaming: PageStreaming;
}

class ModelDetailPageDomain {
    readonly session = new ModelDetailSession();
    readonly capabilityState = new ModelDetailCapabilityState();
    readonly saveRequests = new ChangeNotificationSource();
    readonly saveStatus: ModelDetailSaveStatusState;
    readonly streamManager;
    readonly parameterState;
    readonly parameterView;
    readonly testModalManager;
    readonly #owners: ModelDetailPageDomainOwners;
    readonly #domains;
    readonly #eventController: ModelDetailEventController;
    #icons: Record<string, TrustedHtml> = {};

    constructor(owners: ModelDetailPageDomainOwners) {
        this.#owners = owners;
        const runtime = composeModelDetailRuntime({
            pageDom: owners.pageDom,
            pageResources: owners.pageResources,
            pageElements: owners.pageElements,
            pageLifecycle: owners.pageLifecycle,
            collapsibleCards: owners.collapsibleCards,
            streaming: owners.streaming,
            services: owners.services,
            feedback: owners.feedback,
            storage: owners.storage,
            dom: owners.dom,
            layout: owners.layout,
            modalPresenter: owners.modalPresenter,
            router: owners.router,
            saveRequests: this.saveRequests,
            session: this.session,
            statusManager: owners.statusManager
        });
        this.streamManager = runtime.streamManager;
        this.parameterState = runtime.parameterState;
        this.parameterView = runtime.parameterView;
        this.testModalManager = runtime.testModalManager;
        this.#domains = composeModelDetailDomains({
            api: owners.api,
            capabilityState: this.capabilityState,
            dom: owners.dom,
            feedback: owners.feedback,
            modalPresenter: owners.modalPresenter,
            pageContext: owners.pageContext,
            pageDom: owners.pageDom,
            pageElements: owners.pageElements,
            pageLifecycle: owners.pageLifecycle,
            pageResources: owners.pageResources,
            parameterState: this.parameterState,
            parameterView: this.parameterView,
            router: owners.router,
            saveRequests: this.saveRequests,
            services: owners.services,
            session: this.session,
            statusManager: owners.statusManager,
            streaming: owners.streaming,
            streamManager: this.streamManager,
            testModalManager: this.testModalManager
        });
        this.saveStatus = this.#domains.saveStatus;
        const events = {
            session: this.session,
            pageDom: owners.pageDom,
            pageResources: owners.pageResources,
            pageLifecycle: owners.pageLifecycle,
            feedback: owners.feedback,
            pageElements: owners.pageElements,
            layout: owners.layout,
            router: owners.router,
            parameterView: this.parameterView,
            storage: owners.storage,
            testModalManager: this.testModalManager,
            handleSwitchToParametersAction: () => this.#handleSwitchToParameters(),
            modalPresenter: owners.modalPresenter,
            ensureUi: () => this.#ensureUi(),
            requireModelId: () => this.#requireModelId(),
            streamManager: this.streamManager,
            api: owners.api,
            loadIcons: () => this.#loadIcons(),
            setupHeaderButtons: () => this.#setupHeaderButtons(),
            initializeTabsComponent: () => this.#initializeTabs(),
            onTabChange: (tabId: string) => this.#onTabChange(tabId),
            updateHeaderInfo: () => this.#domains.viewController.updateHeaderInfo(),
            populateModelInfo: () => this.#domains.viewController.populateModelInfo(),
            renderParametersInterface: () => this.#domains.viewController.renderParametersInterface()
        };
        this.#eventController = new ModelDetailEventController({
            session: this.session,
            pageLifecycle: owners.pageLifecycle,
            events,
            view: this.#domains.view,
            actions: this.#domains.actions,
            operations: this.#domains.operations,
            save: this.#domains.save,
            saveStatus: this.saveStatus,
            testModalManager: this.testModalManager,
            ensureUi: () => this.#ensureUi()
        });
        owners.layout.configure({ getActionsMenuBreakpoint: () => 1400, onTabChange: (newTab) => this.#onTabChange(newTab) });
    }

    get icons(): Record<string, TrustedHtml> {
        return this.#icons;
    }

    setModelIdFromParameters(parameters: JsonObject): void {
        const candidate = parameters['id'];
        this.session.modelId = isString(candidate) && candidate.trim() ? candidate : null;
    }

    resetBeforeInitialization(parameters: JsonObject): void {
        resetModelDetailPageBeforeInitialize(this.session, this.capabilityState, parameters);
    }

    async setup(): Promise<void> {
        this.#owners.modalPresenter.requireElement(MODELS_RENAME_MODEL_MODAL_ID);
        this.#owners.modalPresenter.requireElement(MODEL_DETAIL_TEST_MODAL_ID);
        const store = requireCatalogStore();
        await store.ensureCapabilityManifestReady();
        await setupModelDetailPage(this.session, {
            layout: this.#owners.layout,
            pageResources: this.#owners.pageResources,
            loadIcons: () => this.#loadIcons(),
            setupHeaderButtons: () => this.#setupHeaderButtons(),
            notifySaveChanged: () => this.saveRequests.notify(),
            parameterView: this.parameterView,
            router: this.#owners.router,
            initializeTabsComponent: () => this.#initializeTabs(),
            onTabChange: (tabId) => this.#onTabChange(tabId)
        });
        this.#owners.pageResources.track(
            store.subscribeCapabilityManifest(() => {
                if (this.session.model && !this.#owners.pageLifecycle.isDestroyed) this.#domains.viewController.populateDetailCards();
            })
        );
    }

    async loadData(): Promise<void> {
        await loadModelDetailDataAndPendingAction(this.session, { loadModelDetails: () => loadModelDetailData(this.#domains.effects), testModalManager: this.testModalManager });
    }

    bindPageEvents(): void {
        this.#eventController.bind();
    }

    destroy(): void {
        this.#domains.save.dispose();
        this.#domains.unsubscribeSaveRequests();
        this.saveRequests.clear();
        this.saveStatus.reset();
        this.#owners.pageLifecycle.abortListeners('model-detail-destroy');
        cleanupModelDetailPage(this.session, { parameterView: this.parameterView, testModalManager: this.testModalManager });
    }

    #ensureUi(): ModelDetailUi {
        return ensureModelDetailUi(this.session, this.#owners.pageDom, requireModelDetailUi);
    }

    #isVirtualModel(): boolean {
        return this.session.model?.type === 'virtual';
    }

    #requireModelId(): string {
        const candidate = this.session.model?.universalId;
        if (isString(candidate) && candidate.trim()) return candidate.trim();
        throw new Error('ModelDetailPage requires model.universalId for model operations');
    }

    async #loadIcons(): Promise<void> {
        this.#icons = await loadModelDetailIcons();
        this.parameterView.setIcons(this.#icons);
    }

    #requireIcon(iconKey: string): TrustedHtml {
        const markup = this.#icons[iconKey];
        if (!markup || !markup.html.trim()) throw new Error(`ModelDetailPage requires icon "${iconKey}"`);
        return markup;
    }

    #setupHeaderButtons(): void {
        setupModelDetailHeaderButtons({ pageDom: this.#owners.pageDom, ensureUi: () => this.#ensureUi(), requireIconMarkup: (key) => this.#requireIcon(key) });
    }

    async #initializeTabs(): Promise<void> {
        this.#owners.layout.initializeTabs('model-tabs-container', {
            tabs: [
                { id: 'overview', label: i18n.t('modelDetail.tabs.overview') },
                { id: 'parameters', label: i18n.t('modelDetail.tabs.parameters') }
            ],
            activeTab: this.session.activeTab,
            className: 'tabs'
        });
    }

    #onTabChange(newTab: string): void {
        applyModelDetailTabChange(
            this.session,
            {
                pageDom: this.#owners.pageDom,
                ensureUi: () => this.#ensureUi(),
                renderParametersInterface: () => this.#domains.viewController.renderParametersInterface(),
                parameterView: this.parameterView,
                updateBackendDocButtonVisibility: () => this.#domains.viewController.updateBackendDocButtonVisibility()
            },
            newTab
        );
    }

    #handleSwitchToParameters(): void {
        handleModelDetailSwitchToParametersAction(this.session, { layout: this.#owners.layout, isVirtualModel: () => this.#isVirtualModel(), router: this.#owners.router });
    }
}

export { ModelDetailPageDomain };
export type { ModelDetailPageDomainOwners };
