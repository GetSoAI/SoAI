/* SoAI - Frontend application feature registrations [frontend/assets/ts/app/bootstrap/serviceconstruction/featureRegistrations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createBootstrapDisplayServices } from '@app/bootstrap/serviceconstruction/display.ts';
import { createBootstrapInteractiveFeatures } from '@app/bootstrap/serviceconstruction/interactiveFeatures.ts';
import { registerPages } from '@app/bootstrap/pages.ts';
import { CHAT_CONVERSATION_ATTENTION_SERVICE_ID, CHAT_PAGE_PRESENCE_SERVICE_ID, CHAT_RAG_INGESTION_SERVICE_ID, CHAT_STREAM_SERVICE_ID, CHAT_TOOL_ICON_SERVICE_ID } from '@core/chat/protocols.ts';
import { AUTOMATION_RUN_ACTIVITY_SERVICE_ID } from '@core/automation/protocols.ts';
import { registerService } from '@core/serviceRegistration.ts';
import { NOTIFICATIONS_CENTER_SERVICE_ID } from '@core/notifications/protocols.ts';
import { SEARCH_PANEL_SERVICE_ID } from '@core/search/protocols.ts';
import { createStorageService } from '@core/storage/StorageService.ts';
import { TASK_MANAGER_SERVICE_ID } from '@core/tasks/protocols.ts';
import { LOG_STREAM_SERVICE_ID } from '@features/logging/logstreamservice/constants.ts';
import { createCatalogStore } from '@features/catalog/state.ts';
import { FIRST_RUN_MODALS_SERVICE_ID } from '@features/firstrunmodals/public.ts';
import { POWER_ACTION_OVERLAY_SERVICE_ID, RESTART_OVERLAY_SERVICE_ID } from '@features/overlays/public.ts';
import type { FirstRunModalService } from '@core/firstrun/protocols.ts';
import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';

interface FeatureRegistrationsDependencies {
    basePageDependencies: BasePageDependencies;
    interactiveFeatures: ReturnType<typeof createBootstrapInteractiveFeatures>;
    displayServices: ReturnType<typeof createBootstrapDisplayServices>;
    firstRunModals: FirstRunModalService;
    storage: ReturnType<typeof createStorageService>;
    catalogStore: ReturnType<typeof createCatalogStore>;
}

const registerFeatureBootstrapServices = (dependencies: FeatureRegistrationsDependencies): void => {
    registerService(FIRST_RUN_MODALS_SERVICE_ID, dependencies.firstRunModals, {
        moduleId: FIRST_RUN_MODALS_SERVICE_ID,
        initialized: true
    });
    registerService(CHAT_STREAM_SERVICE_ID, dependencies.interactiveFeatures.chatStreamService, {
        moduleId: CHAT_STREAM_SERVICE_ID
    });
    registerService(CHAT_PAGE_PRESENCE_SERVICE_ID, dependencies.interactiveFeatures.chatPagePresence, {
        moduleId: CHAT_PAGE_PRESENCE_SERVICE_ID
    });
    registerService(CHAT_CONVERSATION_ATTENTION_SERVICE_ID, dependencies.interactiveFeatures.chatConversationAttention, {
        moduleId: CHAT_CONVERSATION_ATTENTION_SERVICE_ID
    });
    registerService(CHAT_RAG_INGESTION_SERVICE_ID, dependencies.interactiveFeatures.chatRagIngestionService, {
        moduleId: CHAT_RAG_INGESTION_SERVICE_ID,
        initialized: true
    });
    registerService(CHAT_TOOL_ICON_SERVICE_ID, dependencies.interactiveFeatures.chatToolIconService, {
        moduleId: CHAT_TOOL_ICON_SERVICE_ID
    });
    registerService(AUTOMATION_RUN_ACTIVITY_SERVICE_ID, dependencies.interactiveFeatures.automationRunActivity, {
        moduleId: AUTOMATION_RUN_ACTIVITY_SERVICE_ID
    });
    registerService(LOG_STREAM_SERVICE_ID, dependencies.interactiveFeatures.logStream, {
        moduleId: LOG_STREAM_SERVICE_ID
    });
    registerService('features.overlays.restart', dependencies.interactiveFeatures.restartOverlay, {
        moduleId: RESTART_OVERLAY_SERVICE_ID
    });
    registerService('features.overlays.power', dependencies.interactiveFeatures.powerOverlay, {
        moduleId: POWER_ACTION_OVERLAY_SERVICE_ID
    });
    registerPages({
        basePageDependencies: dependencies.basePageDependencies,
        chatStreamService: dependencies.interactiveFeatures.chatStreamService,
        chatPagePresence: dependencies.interactiveFeatures.chatPagePresence,
        chatConversationAttention: dependencies.interactiveFeatures.chatConversationAttention,
        chatToolIconService: dependencies.interactiveFeatures.chatToolIconService,
        firstRunModals: dependencies.firstRunModals,
        logStream: dependencies.interactiveFeatures.logStream,
        countdownOverlay: dependencies.displayServices.countdownOverlay,
        restartOverlay: dependencies.interactiveFeatures.restartOverlay,
        powerOverlay: dependencies.interactiveFeatures.powerOverlay,
        searchComponent: dependencies.interactiveFeatures.searchPanel,
        catalogStore: dependencies.catalogStore,
        storage: dependencies.storage,
        automationDataService: dependencies.interactiveFeatures.automationDataService,
        automationRunActivity: dependencies.interactiveFeatures.automationRunActivity
    });
    registerService(SEARCH_PANEL_SERVICE_ID, dependencies.interactiveFeatures.searchPanel, {
        moduleId: SEARCH_PANEL_SERVICE_ID,
        initialized: true
    });
    registerService(TASK_MANAGER_SERVICE_ID, dependencies.interactiveFeatures.taskManager, {
        moduleId: TASK_MANAGER_SERVICE_ID,
        initialized: true
    });
    registerService(NOTIFICATIONS_CENTER_SERVICE_ID, dependencies.interactiveFeatures.notificationCenter, {
        moduleId: NOTIFICATIONS_CENTER_SERVICE_ID,
        initialized: true
    });
    registerService('core.layoutShell', dependencies.interactiveFeatures.layoutShell, {
        moduleId: 'core.layoutShell',
        initialized: true
    });
};

export { registerFeatureBootstrapServices };
