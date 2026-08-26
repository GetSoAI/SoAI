/* SoAI - Plugins page controllers contracts [frontend/assets/ts/pages/plugins/controllers/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { CloneModalManager, ConcurrentModalManager, ConfigManager, InfoManager, ManageBackendModalManager, PluginActionHost, PluginDownloadModalManager } from '@features/plugins/public.ts';
import { PluginsDataController } from '@pages/plugins/controllers/dataController.ts';
import { PluginsInteractionController } from '@pages/plugins/controllers/interactionController.ts';
import { PluginsLifecycleController } from '@pages/plugins/controllers/lifecycleController.ts';
import { PluginsOperationsController } from '@pages/plugins/controllers/operationsController.ts';
import { PluginsCollectionController } from '@pages/plugins/controllers/pluginsCollectionController.ts';
import { PluginsCompatibilityController } from '@pages/plugins/controllers/pluginsCompatibilityController.ts';
import type { PluginsRootEventController } from '@pages/plugins/controllers/pluginsRootEventController.ts';
import { PluginsStatsController } from '@pages/plugins/controllers/pluginsStatsController.ts';
import { PluginsTaskActionController } from '@pages/plugins/controllers/pluginsTaskActionController.ts';
import { PluginsProgressController } from '@pages/plugins/controllers/progressController.ts';
import { PluginsStateActionsController } from '@pages/plugins/controllers/stateActionsController.ts';

interface PluginsPageModalManagers {
    downloadModalManager: PluginDownloadModalManager;
    configManager: ConfigManager;
    infoManager: InfoManager;
    concurrentManager: ConcurrentModalManager;
    manageBackendModalManager: ManageBackendModalManager;
    cloneManager: CloneModalManager;
}

interface PluginsPageControllerSet {
    compatibilityController: PluginsCompatibilityController;
    dataController: PluginsDataController;
    collectionController: PluginsCollectionController;
    statsController: PluginsStatsController;
    taskActionController: PluginsTaskActionController;
    progressController: PluginsProgressController;
    operationsController: PluginsOperationsController;
    stateActionsController: PluginsStateActionsController;
    lifecycleController: PluginsLifecycleController;
    interactionController: PluginsInteractionController;
    rootEventController: PluginsRootEventController;
}

interface PluginsPageResourceState {
    progressMetadata: Map<string, Record<string, JsonValue>>;
    activeToggles: Set<string>;
    pendingToggleTargets: Map<string, boolean>;
}

interface PluginsStateActionDispatcher {
    resetCircuitBreaker(plugin: PluginRecord, event?: Event): Promise<void>;
    togglePluginEnabled(plugin: PluginRecord, event?: Event): Promise<void>;
    setCompatibilityOverride(plugin: PluginRecord, override: boolean, event?: Event): Promise<void>;
    stopPlugin(plugin: PluginRecord): Promise<void>;
}

export type { PluginsPageControllerSet, PluginsPageModalManagers, PluginsPageResourceState, PluginsStateActionDispatcher, PluginActionHost };
