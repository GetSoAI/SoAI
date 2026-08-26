/* SoAI - Model detail domain ownership composition [frontend/assets/ts/pages/modeldetail/controllers/page/modelDetailDomainComposition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { PageContext } from '@core/pagecontext/public.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { SaveController } from '@core/save/public.ts';
import type { StatusManager } from '@core/state/public.ts';
import { isString } from '@core/typeGuards.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { TestModalManager } from '@features/modeldetail/public.ts';
import { composeModelDetailActions, type ModelDetailActionsDependencies, type ModelDetailActionsHost } from '@pages/modeldetail/controllers/page/actionEffects.ts';
import { composeModelDetailEffects, fetchModelDetailParametersSnapshot, type ModelDetailEffectsHost } from '@pages/modeldetail/controllers/page/effects/service.ts';
import { ModelDetailViewController } from '@pages/modeldetail/controllers/page/ModelDetailViewController.ts';
import { composeModelDetailOperations } from '@pages/modeldetail/controllers/page/operations/service.ts';
import type { ModelDetailOperationsDependencies, ModelDetailOperationsHost } from '@pages/modeldetail/controllers/page/operations/types.ts';
import { createModelDetailSaveController } from '@pages/modeldetail/controllers/page/saveController.ts';
import { composeModelDetailView } from '@pages/modeldetail/controllers/page/view/mappers.ts';
import type { ModelDetailViewHost } from '@pages/modeldetail/controllers/page/view/types.ts';
import type { ParameterStateManager } from '@pages/modeldetail/controllers/ParameterStateManager.ts';
import type { ParameterViewManager } from '@pages/modeldetail/controllers/ParameterViewManager.ts';
import { ensureModelDetailUi } from '@pages/modeldetail/controllers/page/guards.ts';
import { requireModelDetailUi } from '@pages/modeldetail/dom.ts';
import type { ModelDetailCapabilityState } from '@pages/modeldetail/state/ModelDetailCapabilityState.ts';
import type { ChangeNotificationSource } from '@core/primitives/changeNotificationSource.ts';
import { ModelDetailSaveStatusState } from '@pages/modeldetail/state/ModelDetailSaveStatusState.ts';
import type { ModelDetailSession } from '@pages/modeldetail/state/ModelDetailSession.ts';

interface ModelDetailDomainOwners {
    api: ModelDetailActionsDependencies['api'] & ModelDetailOperationsDependencies['api'];
    capabilityState: ModelDetailCapabilityState;
    dom: ModelDetailOperationsDependencies['dom'];
    feedback: PageFeedback;
    modalPresenter: ModalPresenterApi;
    pageContext: PageContext;
    pageDom: PageDom;
    pageElements: PageUi;
    pageLifecycle: PageLifecycle;
    pageResources: PageResources;
    parameterState: ParameterStateManager;
    parameterView: ParameterViewManager;
    router: ModelDetailOperationsDependencies['router'];
    saveRequests: ChangeNotificationSource;
    services: PageServices;
    session: ModelDetailSession;
    statusManager: StatusManager;
    streaming: PageStreaming;
    streamManager: ModelDetailActionsDependencies['streamManager'] & ModelDetailEffectsHost['state']['streamManager'];
    testModalManager: TestModalManager;
}

interface ModelDetailDomains {
    actions: ModelDetailActionsHost;
    effects: ModelDetailEffectsHost;
    operations: ModelDetailOperationsHost;
    save: SaveController;
    saveStatus: ModelDetailSaveStatusState;
    unsubscribeSaveRequests: () => void;
    view: ModelDetailViewHost;
    viewController: ModelDetailViewController;
}

const composeModelDetailDomains = (owners: ModelDetailDomainOwners): ModelDetailDomains => {
    const saveStatus = new ModelDetailSaveStatusState();
    const ensureUi = () => ensureModelDetailUi(owners.session, owners.pageDom, requireModelDetailUi);
    const isVirtualModel = () => owners.session.model?.type === 'virtual';
    const requireModelId = (): string => {
        const candidate = owners.session.model?.universalId;
        if (isString(candidate) && candidate.trim()) return candidate.trim();
        throw new Error('ModelDetailPage requires model.universalId for model operations');
    };
    const getCapabilityState = () => owners.capabilityState.get(owners.session.model, owners.session.model ? requireModelId() : null);
    const reconcileCapabilityState = (model: ModelRecord | null): void => {
        if (!model) {
            owners.capabilityState.reset();
            return;
        }
        owners.capabilityState.rehydrate(model, requireModelId());
    };
    const view = composeModelDetailView({
        session: owners.session,
        pageDom: owners.pageDom,
        pageElements: owners.pageElements,
        services: owners.services,
        parameterState: owners.parameterState,
        streamManager: owners.streamManager,
        ensureUi,
        isVirtualModel,
        sanitizeAttribute: (value) => owners.pageContext.sanitizer.attribute(value),
        statusManager: owners.statusManager,
        modalPresenter: owners.modalPresenter,
        getOpenAICapabilityState: getCapabilityState,
        resolveOpenAICapabilityLabel: (category, token) => owners.capabilityState.resolveLabel(category, token)
    });
    const viewController = new ModelDetailViewController({ session: owners.session, pageDom: owners.pageDom, view, parameterState: owners.parameterState, parameterView: owners.parameterView, saveStatus });
    const operations = composeModelDetailOperations({
        session: owners.session,
        pageDom: owners.pageDom,
        pageResources: owners.pageResources,
        pageElements: owners.pageElements,
        pageLifecycle: owners.pageLifecycle,
        streaming: owners.streaming,
        feedback: owners.feedback,
        ensureUi,
        dom: owners.dom,
        requireModelId,
        isVirtualModel,
        api: owners.api,
        router: owners.router
    });
    const effects = composeModelDetailEffects({
        session: owners.session,
        view,
        pageResources: owners.pageResources,
        pageLifecycle: owners.pageLifecycle,
        streaming: owners.streaming,
        feedback: owners.feedback,
        get isDestroyed() {
            return owners.pageLifecycle.isDestroyed;
        },
        streamManager: owners.streamManager,
        parameterView: owners.parameterView,
        reconcileOpenAICapabilityState: reconcileCapabilityState,
        setLoadError: (error) => {
            owners.session.loadError = error;
        },
        applyParametersPayload: (payload) => viewController.applyParametersPayload(payload),
        populateModelInfo: () => viewController.populateModelInfo(),
        renderParametersInterface: () => viewController.renderParametersInterface(),
        updateBackendDocButtonVisibility: () => viewController.updateBackendDocButtonVisibility(),
        updateTestPluginStatusDisplay: () => owners.testModalManager.updatePluginStatusDisplay(),
        populateDetailCards: () => viewController.populateDetailCards(),
        setInfo: (id, value) => viewController.setInfo(id, value),
        router: owners.router
    });
    const actions = composeModelDetailActions({
        session: owners.session,
        pageResources: owners.pageResources,
        feedback: owners.feedback,
        pageLifecycle: owners.pageLifecycle,
        parameterState: owners.parameterState,
        parameterView: owners.parameterView,
        requireModelId,
        streamManager: owners.streamManager,
        api: owners.api,
        isVirtualModel,
        getOpenAICapabilityState: getCapabilityState,
        applySavedOpenAICapabilityModel: (model) => {
            owners.session.model = model;
            owners.capabilityState.rehydrate(model, requireModelId());
        },
        applyParametersPayload: (payload) => viewController.applyParametersPayload(payload),
        populateDetailCards: () => viewController.populateDetailCards(),
        notifySaveChanged: () => owners.saveRequests.notify(),
        fetchParametersSnapshot: () => fetchModelDetailParametersSnapshot(effects)
    });
    const save = createModelDetailSaveController({ actions, getOpenAICapabilityState: getCapabilityState });
    const unsubscribeSaveRequests = owners.saveRequests.subscribe(() => save.notifyChanged());
    return { actions, effects, operations, save, saveStatus, unsubscribeSaveRequests, view, viewController };
};

export { composeModelDetailDomains };
export type { ModelDetailDomainOwners, ModelDetailDomains };
