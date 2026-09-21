/* SoAI - Application service construction and registration [frontend/assets/ts/app/bootstrap/registerServices.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createBootstrapDisplayServices } from '@app/bootstrap/serviceconstruction/display.ts';
import { registerCoreBootstrapServices } from '@app/bootstrap/serviceconstruction/coreRegistrations.ts';
import { registerFeatureBootstrapServices } from '@app/bootstrap/serviceconstruction/featureRegistrations.ts';
import { createBootstrapFoundationServices } from '@app/bootstrap/serviceconstruction/foundation.ts';
import { createBootstrapInteractiveFeatures } from '@app/bootstrap/serviceconstruction/interactiveFeatures.ts';
import { requireFrontendEditionComposition } from '@app/edition/frontendEditionComposition.ts';
import { createModalStorageService, createRouterStateService, createStorageApiService, createStorageStateService, createStreamAuthService, createStreamStateService } from '@app/bootstrap/serviceconstruction/serviceAdapters.ts';
import { getAppModalDefinitions } from '@app/bootstrap/modalDefinitions.ts';
import { CHAT_MEMORY_PROFILE_FIRST_RUN_REGISTRATION } from '@features/chat/public.ts';
import { AuthManager } from '@core/auth/public.ts';
import { createDashboardIntroDriverPresenceState, createDashboardIntroFirstRunRegistration } from '@features/firstrunmodals/public.ts';
import { createFirstRunModalsService } from '@features/firstrunmodals/service.ts';
import { createConnectionState } from '@core/connectionstate/service.ts';
import { createConnectionStatus } from '@core/connectionstatus/public.ts';
import { dom } from '@core/dom/dom.ts';
import { loadingState } from '@core/loadingState.ts';
import { ErrorBoundary } from '@core/ErrorBoundary.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { setApiNotificationBridge } from '@core/api/notificationBridge.ts';
import type { APIErrorMetadataValue } from '@core/apiError.ts';
import { createModalPresenterService } from '@core/modals/modalPresenter.ts';
import { OperationErrorNotifier, notifyHandledOperationError } from '@core/operationErrorNotifier.ts';
import { PageOutlet } from '@core/pageoutlet/public.ts';
import { createRealtimeService } from '@core/realtime/public.ts';
import { StreamManager } from '@core/realtime/streammanager/StreamManager.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { Router } from '@core/routing/router/Router.ts';
import { registerService } from '@core/serviceRegistration.ts';
import { createSoaiOsCapabilities } from '@core/soaiOsCapabilities.ts';
import { createStorageService } from '@core/storage/StorageService.ts';
import { createSecretInputToggleService } from '@core/ui/secretInput.ts';
import { createSearchFieldActionService } from '@core/ui/searchField.ts';
import { createTooltipService } from '@core/ui/tooltips/public.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';
import { initializeSoundEffectsUnlock } from '@core/ui/sound/engine.ts';
import { PLUGINS_INTRO_FIRST_RUN_REGISTRATION } from '@features/plugins/public.ts';
import type { LanguageService } from '@core/routing/pages/pagetypes/public.ts';
import { ClientDataHub } from '@core/data/ClientDataHub.ts';
import { COLLECTION_CHANNEL_CATALOG } from '@core/data/clientdatahub/channelCatalog.ts';
import { createCatalogStore } from '@features/catalog/state.ts';

export function registerAllServices(languageService: LanguageService): void {
    initializeSoundEffectsUnlock();

    const foundation = createBootstrapFoundationServices();
    registerService('core.apiClient', foundation.apiClient, {
        moduleId: 'core.apiClient',
        initialized: true
    });
    registerService('core.state', foundation.stateManager, {
        moduleId: 'core.state'
    });

    const displayServices = createBootstrapDisplayServices();

    registerService('core.maintenanceCoordinator', foundation.maintenanceCoordinator);
    registerService('core.branding', foundation.branding);
    const tooltipService = createTooltipService();
    registerService('core.tooltipService', tooltipService);
    const secretInputToggleService = createSecretInputToggleService({ documentRef: dom.getDocument() });
    secretInputToggleService.initialize();
    registerService('core.secretInputToggle', secretInputToggleService, {
        moduleId: 'core.secretInputToggle',
        initialized: true
    });
    const searchFieldActionService = createSearchFieldActionService(dom.getDocument());
    searchFieldActionService.initialize();
    registerService('core.searchFieldActions', searchFieldActionService, {
        moduleId: 'core.searchFieldActions',
        initialized: true
    });

    setApiNotificationBridge({
        showNotification: (message: string, type: 'success' | 'error' | 'warning' | 'danger' | 'info', durationMs: number) => showNotification(message, type, durationMs),
        notifyHandledOperationError: (error: APIErrorMetadataValue) => notifyHandledOperationError(error)
    });

    const storage = createStorageService({
        apiClient: createStorageApiService(foundation.apiClient),
        stateManager: createStorageStateService(foundation.stateManager)
    });
    const connectionState = createConnectionState({ storage });

    const authManager = new AuthManager();
    registerService('core.auth', authManager, {
        moduleId: 'core.auth'
    });
    const soaiOsCapabilities = createSoaiOsCapabilities({
        api: foundation.apiClient,
        auth: authManager
    });
    const connectionStatus = createConnectionStatus();
    registerService('core.connectionStatus', connectionStatus, {
        moduleId: 'core.connectionStatus'
    });
    const realtime = createRealtimeService();
    const streamManager = new StreamManager({
        apiClient: foundation.apiClient,
        state: createStreamStateService(foundation.stateManager),
        auth: createStreamAuthService(authManager),
        connectionState
    });
    const clientDataHub = new ClientDataHub({
        definitions: COLLECTION_CHANNEL_CATALOG,
        subscribeResourceState: (resource, listener) => streamManager.subscriptions.subscribeResourceState(resource, listener),
        ensureResourceReady: async (resource) => streamManager.resources.ensureResourceStarted(resource),
        refreshResource: async (resource) => streamManager.resources.refresh(resource, { allowDiscovery: true, throwOnError: true })
    });
    const catalogStore = createCatalogStore(clientDataHub, streamManager.tasks);
    const dashboardIntroDriverPresence = createDashboardIntroDriverPresenceState();
    const dashboardIntroProduct = requireFrontendEditionComposition().createDashboardIntro(foundation.apiClient.os, soaiOsCapabilities);
    const dashboardIntroFirstRunRegistration = createDashboardIntroFirstRunRegistration({
        driverPresence: dashboardIntroDriverPresence,
        product: dashboardIntroProduct
    });
    const modalDefinitions = getAppModalDefinitions({ storage, apiClient: foundation.apiClient, dashboardIntroDriverPresence, dashboardIntroProduct, streamManager: streamManager.resources });
    const modalPresenter = createModalPresenterService({ storage: createModalStorageService(storage), definitions: modalDefinitions });
    const router = new Router({
        dom,
        storage,
        auth: authManager,
        api: foundation.apiClient,
        streamManager: streamManager.resources,
        state: createRouterStateService(foundation.stateManager),
        cleanupManager: foundation.cleanupManager,
        ResourceTracker,
        errorHandler,
        PageOutlet,
        ErrorBoundary,
        modalPresenter,
        componentRegistry: foundation.componentRegistry.components,
        pageRegistry: foundation.pageRegistry,
        getSidebarService: () => displayServices.sidebarComponent
    });
    const operationErrorNotifier = new OperationErrorNotifier(streamManager.tasks);
    const firstRunModals = createFirstRunModalsService({
        modalPresenter,
        storage,
        registrations: [CHAT_MEMORY_PROFILE_FIRST_RUN_REGISTRATION, dashboardIntroFirstRunRegistration, PLUGINS_INTRO_FIRST_RUN_REGISTRATION]
    });
    registerCoreBootstrapServices({
        foundation,
        displayServices,
        storage,
        connectionState,
        soaiOsCapabilities,
        realtime,
        streamManager,
        router,
        operationErrorNotifier,
        modalPresenter,
        clientDataHub,
        catalogStore
    });
    const interactiveFeatures = createBootstrapInteractiveFeatures({
        apiClient: foundation.apiClient,
        storage,
        router,
        authManager,
        connectionStatus,
        maintenanceCoordinator: foundation.maintenanceCoordinator,
        modalPresenter,
        mainStatusMonitor: foundation.mainStatusMonitor,
        componentRegistry: foundation.componentRegistry,
        header: displayServices.header,
        sidebarComponent: displayServices.sidebarComponent,
        overlay: displayServices.overlay
    });
    registerFeatureBootstrapServices({
        basePageDependencies: {
            api: foundation.apiClient,
            auth: authManager,
            dom,
            languageService,
            loadingState,
            router,
            stateManager: foundation.stateManager,
            storage
        },
        interactiveFeatures,
        displayServices,
        firstRunModals,
        storage,
        catalogStore
    });
}
