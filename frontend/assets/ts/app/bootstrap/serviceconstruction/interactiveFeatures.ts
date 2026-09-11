/* SoAI - Frontend application interactive features [frontend/assets/ts/app/bootstrap/serviceconstruction/interactiveFeatures.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LayoutShell, type ComponentInstance } from '@app/bootstrap/LayoutShell.ts';
import { createAutomationRunConversationRedirectMiddleware } from '@app/bootstrap/navigation/automationRunRedirect.ts';
import { createSearchStaticContributors } from '@app/bootstrap/serviceconstruction/searchStaticContributors.ts';
import { getApiClient } from '@core/api/service.ts';
import { getAuthManager } from '@core/auth/public.ts';
import { ComponentRegistry } from '@core/componentsupport/public.ts';
import { createConnectionStatus } from '@core/connectionstatus/public.ts';
import { requireDocument } from '@core/environment/public.ts';
import { LayoutHeader } from '@core/layout/header/Header.ts';
import { LayoutSidebar } from '@core/layout/sidebar/Sidebar.ts';
import { getMainStatusMonitor } from '@core/mainstatusmonitor/public.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { createMaintenanceCoordinator } from '@core/maintenanceCoordinator.ts';
import { NOTIFICATIONS_CENTER_SERVICE_ID } from '@core/notifications/protocols.ts';
import { getStatusManager } from '@core/state/public.ts';
import { getStreamRuntime } from '@core/realtime/streammanager/public.ts';
import { Router } from '@core/routing/router/Router.ts';
import { SEARCH_PANEL_SERVICE_ID } from '@core/search/protocols.ts';
import { createStorageService } from '@core/storage/StorageService.ts';
import { TASK_MANAGER_SERVICE_ID } from '@core/tasks/protocols.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';
import { AutomationApiService, type AutomationDataService } from '@features/automation/public.ts';
import { AutomationRunActivityService } from '@features/automation/runactivity/service.ts';
import { createHardwareSearchContributor } from '@features/hardware/search/contributor.ts';
import { ChatPagePresenceService } from '@features/chat/background/ChatPagePresenceService.ts';
import { ChatConversationAttentionService } from '@features/chat/background/ChatConversationAttentionService.ts';
import { ChatRagIngestionService } from '@features/chat/ragingestion/ChatRagIngestionService.ts';
import { ChatStreamService } from '@features/chat/chatstreamservice/service.ts';
import { ChatToolIconService } from '@features/chat/ChatToolIconService.ts';
import { LogStream } from '@features/logging/logstreamservice/service.ts';
import { LiveStatusOverlay } from '@features/indicators/service.ts';
import { createPowerActionOverlay } from '@features/overlays/PowerAction.ts';
import { RestartOverlay } from '@features/overlays/restart/service.ts';
import { RESTART_OVERLAY_SERVICE_ID } from '@features/overlays/public.ts';
import { SearchComponent } from '@features/search/SearchPanel.ts';
import { openPromptContentPreview } from '@features/prompts/public.ts';
import { TaskManager } from '@features/tasks/TaskManager.ts';
import { TaskManagerStore } from '@features/tasks/taskmanagerstore/service.ts';
import { LIVE_STATUS_OVERLAY_SERVICE_ID } from '@features/indicators/constants.ts';
import { NotificationCenter } from '@features/notifications/public.ts';
import { sendWebSocketMessage } from '@core/websocketclient/service.ts';

interface BootstrapInteractiveFeatureDependencies {
    apiClient: ReturnType<typeof getApiClient>;
    storage: ReturnType<typeof createStorageService>;
    router: Router;
    authManager: ReturnType<typeof getAuthManager>;
    connectionStatus: ReturnType<typeof createConnectionStatus>;
    maintenanceCoordinator: ReturnType<typeof createMaintenanceCoordinator>;
    modalPresenter: ModalPresenterApi;
    mainStatusMonitor: ReturnType<typeof getMainStatusMonitor>;
    componentRegistry: ComponentRegistry;
    header: LayoutHeader;
    sidebarComponent: LayoutSidebar;
    overlay: LiveStatusOverlay;
}

interface BootstrapInteractiveFeatures {
    chatStreamService: ChatStreamService;
    chatPagePresence: ChatPagePresenceService;
    chatConversationAttention: ChatConversationAttentionService;
    chatRagIngestionService: ChatRagIngestionService;
    chatToolIconService: ChatToolIconService;
    automationDataService: AutomationDataService;
    automationRunActivity: AutomationRunActivityService;
    logStream: LogStream;
    restartOverlay: RestartOverlay;
    powerOverlay: ReturnType<typeof createPowerActionOverlay>;
    searchPanel: SearchComponent;
    taskManager: TaskManager;
    notificationCenter: NotificationCenter;
    layoutShell: LayoutShell;
}

const createBootstrapInteractiveFeatures = (dependencies: BootstrapInteractiveFeatureDependencies): BootstrapInteractiveFeatures => {
    const stream = getStreamRuntime();
    const chatStreamService = new ChatStreamService({
        apiClient: dependencies.apiClient,
        presentationInterests: stream.connection
    });
    const chatPagePresence = new ChatPagePresenceService();
    const chatConversationAttention = new ChatConversationAttentionService({ stream, sendMessage: sendWebSocketMessage });
    const chatRagIngestionService = new ChatRagIngestionService({ api: dependencies.apiClient });
    const chatToolIconService = new ChatToolIconService(dependencies.apiClient);
    const automationDataService = new AutomationApiService(dependencies.apiClient);
    const automationRunActivity = new AutomationRunActivityService(dependencies.apiClient);
    dependencies.router.useNavigationMiddleware(createAutomationRunConversationRedirectMiddleware(automationDataService), { priority: 95 });
    const logStream = new LogStream({ api: dependencies.apiClient });
    const restartOverlay = new RestartOverlay();
    const powerOverlay = createPowerActionOverlay({
        api: dependencies.apiClient,
        maintenanceCoordinator: dependencies.maintenanceCoordinator
    });
    const searchPanel = new SearchComponent({
        apiClient: dependencies.apiClient,
        storage: dependencies.storage,
        router: dependencies.router,
        connectionStatus: dependencies.connectionStatus,
        auth: dependencies.authManager,
        searchContributors: [createHardwareSearchContributor()],
        staticContributors: createSearchStaticContributors({ apiClient: dependencies.apiClient, authManager: dependencies.authManager }),
        openPromptPreview: async (promptId: string): Promise<boolean> =>
            await openPromptContentPreview(
                {
                    promptsApi: dependencies.apiClient.webui.prompts,
                    requireModalElement: (id) => dependencies.modalPresenter.requireElement(id),
                    getDocument: () => requireDocument(),
                    showNotification: (message, type, duration) => {
                        showNotification(message, type, duration);
                    }
                },
                promptId
            )
    });
    const taskManager = new TaskManager({
        dom: { getDocument: () => requireDocument() },
        statusManager: getStatusManager(),
        apiClient: dependencies.apiClient,
        stream,
        createStore: () => new TaskManagerStore({ stream }),
        storage: dependencies.storage
    });
    const notificationCenter = new NotificationCenter({
        dom: { getDocument: () => requireDocument() },
        header: dependencies.header,
        apiClient: dependencies.apiClient,
        stream,
        taskOperations: taskManager
    });
    const componentLookup = new Map<string, ComponentInstance>([
        ['core.layout.header', dependencies.header],
        ['core.layout.sidebar', dependencies.sidebarComponent],
        [NOTIFICATIONS_CENTER_SERVICE_ID, notificationCenter],
        [TASK_MANAGER_SERVICE_ID, taskManager],
        [SEARCH_PANEL_SERVICE_ID, searchPanel],
        [LIVE_STATUS_OVERLAY_SERVICE_ID, dependencies.overlay],
        [RESTART_OVERLAY_SERVICE_ID, restartOverlay]
    ]);
    const layoutShell = new LayoutShell({
        mainStatusMonitor: dependencies.mainStatusMonitor,
        componentRegistry: dependencies.componentRegistry,
        componentLookup
    });

    return {
        chatStreamService,
        chatPagePresence,
        chatConversationAttention,
        chatRagIngestionService,
        chatToolIconService,
        automationDataService,
        automationRunActivity,
        logStream,
        restartOverlay,
        powerOverlay,
        searchPanel,
        taskManager,
        notificationCenter,
        layoutShell
    };
};

export { createBootstrapInteractiveFeatures };
