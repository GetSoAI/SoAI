/* SoAI - Frontend application core registrations [frontend/assets/ts/app/bootstrap/serviceconstruction/coreRegistrations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createBootstrapDisplayServices } from '@app/bootstrap/serviceconstruction/display.ts';
import { createBootstrapFoundationServices } from '@app/bootstrap/serviceconstruction/foundation.ts';
import { SYSTEM_LIMITS_SERVICE_ID } from '@core/api/systemLimitsService.ts';
import { createConnectionState } from '@core/connectionstate/service.ts';
import { configureCollection } from '@core/componentsupport/public.ts';
import { dom, DomObserver, getDomUpdateService, uiElementServiceModule } from '@core/dom/dom.ts';
import { operationProgress } from '@core/operationprogress/public.ts';
import { ErrorBoundary } from '@core/ErrorBoundary.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { MAIN_STATE_SERVICE_ID } from '@core/indicators/protocols.ts';
import { LifecycleModel } from '@core/LifecycleModel.ts';
import { LOG_VALIDATION_SERVICE_ID } from '@core/logvalidation/public.ts';
import { OperationErrorNotifier } from '@core/operationErrorNotifier.ts';
import { PageHost } from '@core/pagehost/service.ts';
import { PageOutlet } from '@core/pageoutlet/public.ts';
import type { RealtimeService } from '@core/realtime/public.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { BasePage } from '@core/routing/pages/basepage/public.ts';
import { Router } from '@core/routing/router/Router.ts';
import { runtimeEnv } from '@core/runtimeenv/public.ts';
import { securityApi } from '@core/security/public.ts';
import { registerService } from '@core/serviceRegistration.ts';
import { createSoaiOsCapabilities } from '@core/soaiOsCapabilities.ts';
import { speedTest } from '@core/speedTest.ts';
import { createStorageService } from '@core/storage/StorageService.ts';
import { subscriptionManager } from '@core/subscriptionmanager/service.ts';
import { SyntaxHighlighter } from '@core/syntaxhighlighter/public.ts';
import { createModalPresenterService, MODAL_PRESENTER_SERVICE_ID } from '@core/modals/modalPresenter.ts';
import { createDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { DIALOGS_SERVICE_ID } from '@core/ui/modals/dialogs/ids.ts';
import { createContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import { CONTENT_PREVIEW_SERVICE_ID } from '@core/ui/modals/contentpreview/constants.ts';
import { ICON_SERVICE_ID } from '@core/ui/icons/iconservice/public.ts';
import { primitives } from '@core/uiprimitives/public.ts';
import type { StreamManager } from '@core/realtime/streammanager/StreamManager.ts';
import { CATALOG_STORE_SERVICE_ID } from '@features/catalog/service.ts';
import { LIVE_STATUS_OVERLAY_SERVICE_ID } from '@features/indicators/constants.ts';
import { COUNTDOWN_OVERLAY_SERVICE_ID } from '@features/overlays/public.ts';
import type { ClientDataHub } from '@core/data/ClientDataHub.ts';
import { CLIENT_DATA_HUB_SERVICE_ID } from '@core/data/clientdatahub/runtime.ts';
import type { createCatalogStore } from '@features/catalog/state.ts';

interface CoreRegistrationsDependencies {
    foundation: ReturnType<typeof createBootstrapFoundationServices>;
    displayServices: ReturnType<typeof createBootstrapDisplayServices>;
    storage: ReturnType<typeof createStorageService>;
    connectionState: ReturnType<typeof createConnectionState>;
    soaiOsCapabilities: ReturnType<typeof createSoaiOsCapabilities>;
    realtime: RealtimeService;
    streamManager: StreamManager;
    router: Router;
    operationErrorNotifier: OperationErrorNotifier;
    modalPresenter: ReturnType<typeof createModalPresenterService>;
    clientDataHub: ClientDataHub;
    catalogStore: ReturnType<typeof createCatalogStore>;
}

const registerCoreBootstrapServices = (dependencies: CoreRegistrationsDependencies): void => {
    registerService('core.dom', dom);
    registerService('core.domUpdateService', getDomUpdateService());
    registerService('core.domObserver', DomObserver);
    registerService('core.uiElementService', uiElementServiceModule);
    registerService('core.errorHandler', errorHandler);
    registerService('core.licenseService', dependencies.foundation.licenseService);
    registerService('core.operationProgress', operationProgress);
    registerService('core.subscriptionManager', subscriptionManager);
    registerService('core.mainStatusMonitor', dependencies.foundation.mainStatusMonitor);
    registerService('core.runtimeEnv', runtimeEnv);
    registerService('core.eventBus', dependencies.foundation.globalEventBus);
    registerService('core.componentRegistry', dependencies.foundation.componentRegistry);
    registerService('core.componentSupport', dependencies.foundation.componentSupport);
    registerService('core.collectionSupport', { configure: configureCollection });
    registerService(CLIENT_DATA_HUB_SERVICE_ID, dependencies.clientDataHub, {
        moduleId: CLIENT_DATA_HUB_SERVICE_ID,
        initialized: true
    });
    registerService(CATALOG_STORE_SERVICE_ID, dependencies.catalogStore, {
        moduleId: CATALOG_STORE_SERVICE_ID,
        initialized: true
    });
    registerService('core.security', securityApi);
    registerService(ICON_SERVICE_ID, dependencies.foundation.iconService, {
        moduleId: ICON_SERVICE_ID,
        initialized: true
    });
    registerService(LOG_VALIDATION_SERVICE_ID, dependencies.foundation.logValidation, {
        moduleId: LOG_VALIDATION_SERVICE_ID,
        initialized: true
    });
    registerService(SYSTEM_LIMITS_SERVICE_ID, dependencies.foundation.systemLimitsService, {
        moduleId: SYSTEM_LIMITS_SERVICE_ID,
        initialized: true
    });
    registerService('core.basePage', BasePage);
    registerService('core.resourceTracker', ResourceTracker, {
        moduleId: 'core.resourceTracker'
    });
    registerService('core.errorBoundary', ErrorBoundary, {
        moduleId: 'core.errorBoundary'
    });
    registerService('core.pageOutlet', PageOutlet, {
        moduleId: 'core.pageOutlet'
    });
    registerService('core.storage', dependencies.storage, {
        moduleId: 'core.storage'
    });
    registerService('core.connectionState', dependencies.connectionState, {
        moduleId: 'core.connectionState'
    });
    registerService(MODAL_PRESENTER_SERVICE_ID, dependencies.modalPresenter, {
        moduleId: MODAL_PRESENTER_SERVICE_ID,
        initialized: true
    });
    const dialogsService = createDialogsService();
    registerService(DIALOGS_SERVICE_ID, dialogsService, {
        moduleId: DIALOGS_SERVICE_ID,
        initialized: true
    });
    const contentPreviewModalService = createContentPreviewModalService();
    registerService(CONTENT_PREVIEW_SERVICE_ID, contentPreviewModalService, {
        moduleId: CONTENT_PREVIEW_SERVICE_ID,
        initialized: true
    });
    registerService('core.soaiOsCapabilities', dependencies.soaiOsCapabilities, {
        moduleId: 'core.soaiOsCapabilities'
    });
    registerService('core.streamLifecycle', dependencies.streamManager, {
        moduleId: 'core.streamLifecycle'
    });
    registerService('core.streamResources', dependencies.streamManager.resources, {
        moduleId: 'core.streamResources'
    });
    registerService('core.streamSubscriptions', dependencies.streamManager.subscriptions, {
        moduleId: 'core.streamSubscriptions'
    });
    registerService('core.streamTasks', dependencies.streamManager.tasks, {
        moduleId: 'core.streamTasks'
    });
    registerService('core.streamConnection', dependencies.streamManager.connection, {
        moduleId: 'core.streamConnection'
    });
    registerService('core.operationErrorNotifier', dependencies.operationErrorNotifier, {
        moduleId: 'core.operationErrorNotifier'
    });
    registerService('core.realtime', dependencies.realtime, {
        moduleId: 'core.realtime'
    });
    registerService('core.router', dependencies.router, {
        moduleId: 'core.router',
        initialized: true
    });
    registerService('core.pageRegistry', dependencies.foundation.pageRegistry, {
        moduleId: 'core.pageRegistry'
    });
    registerService('core.pageHost', PageHost, {
        moduleId: 'core.pageHost'
    });
    registerService('core.uiPrimitives', primitives, {
        moduleId: 'core.uiPrimitives'
    });
    registerService('core.speedTest', speedTest, {
        moduleId: 'core.speedTest'
    });
    registerService('core.layoutManager', dependencies.foundation.layoutRuntime, {
        moduleId: 'core.layoutManager'
    });
    registerService('core.lifecycleModel', LifecycleModel, {
        moduleId: 'core.lifecycleModel'
    });
    const syntaxHighlighter = new SyntaxHighlighter(() => dependencies.storage.getCodeRecognitionEnabled());
    registerService('core.syntaxHighlighter', syntaxHighlighter, {
        moduleId: 'core.syntaxHighlighter',
        initialized: true
    });
    registerService('core.layout.header', dependencies.displayServices.header, {
        moduleId: 'core.layout.header'
    });
    registerService('core.layout.sidebar', dependencies.displayServices.sidebarComponent, {
        moduleId: 'core.layout.sidebar'
    });
    registerService(LIVE_STATUS_OVERLAY_SERVICE_ID, dependencies.displayServices.overlay, {
        moduleId: LIVE_STATUS_OVERLAY_SERVICE_ID
    });
    registerService(MAIN_STATE_SERVICE_ID, dependencies.displayServices.mainStateIndicatorComponent, {
        moduleId: MAIN_STATE_SERVICE_ID
    });
    registerService('features.overlays.countdown', dependencies.displayServices.countdownOverlay, {
        moduleId: COUNTDOWN_OVERLAY_SERVICE_ID
    });
};

export { registerCoreBootstrapServices };
