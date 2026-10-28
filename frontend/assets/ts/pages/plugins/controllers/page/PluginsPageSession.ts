/* SoAI - Plugins page domain state ownership [frontend/assets/ts/pages/plugins/controllers/page/PluginsPageSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createRecentItemTracker, type RecentItemTracker } from '@core/collectionpage/recentItemTracker.ts';
import type { CardPageController } from '@core/routing/pages/collections/cardgridpage/public.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { resolveInitialCollectionDisplayMode, type CollectionDisplayMode, type ViewModeController } from '@core/uiprimitives/viewmode/public.ts';
import type { CatalogStore } from '@features/catalog/public.ts';
import type { PluginCardRenderer } from '@pages/plugins/rendering/cardrenderer/service.ts';
import type { PluginBackendUpdateStatus } from '@core/api/contracts/pluginManagementContracts.ts';
import { CollectionGroupingState } from '@core/collectionpage/collectionGroupingState.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { canManagePluginBackends } from '@core/plugins/backendUpdateAccess.ts';
import { loadWebuiPermissionsSnapshot } from '@core/access/webuiPermissions.ts';
import type { BackendUpdateAccess } from '@core/plugins/backendUpdates.ts';
import { ChangeNotificationSource } from '@core/primitives/changeNotificationSource.ts';
import { getRestartState, subscribeRestartState } from '@core/restartStateService.ts';
import { requireTaskOperationsApi } from '@core/tasks/serviceAccess.ts';

const PLUGINS_VIEW_MODE_STORAGE_KEY = 'soai.plugins.viewMode';

class PluginsPageSession {
    readonly catalogStore: CatalogStore;
    readonly recentItems: RecentItemTracker = createRecentItemTracker();
    readonly progressMetadata = new Map<string, JsonObject>();
    readonly activeToggles = new Set<string>();
    readonly pendingToggleTargets = new Map<string, boolean>();
    readonly deletingItems = new Set<string>();
    readonly grouping = new CollectionGroupingState<PluginRecord>();
    #coreConfigCache: JsonObject | null = null;
    readonly #backendUpdateChanges = new ChangeNotificationSource();
    #canAdministerPlugins = false;

    get coreConfigCache(): JsonObject | null {
        return this.#coreConfigCache;
    }
    set coreConfigCache(value: JsonObject | null) {
        this.#coreConfigCache = value;
        this.#backendUpdateChanges.notify();
    }
    get canAdministerPlugins(): boolean {
        return this.#canAdministerPlugins;
    }
    set canAdministerPlugins(value: boolean) {
        if (value === this.#canAdministerPlugins) return;
        this.#canAdministerPlugins = value;
        this.#backendUpdateChanges.notify();
    }

    subscribeBackendUpdateAccess(listener: () => void): () => void {
        const disposers = [this.#backendUpdateChanges.subscribe(listener), subscribeRestartState(listener, { immediate: false }), requireTaskOperationsApi().subscribeOperations({}, listener)];
        return () => {
            for (const dispose of disposers) dispose();
        };
    }
    readonly #permissionToken = new SequenceToken();
    coreConfigPromise: Promise<void> | null = null;
    maxConcurrentPlugins: number | null = null;
    concurrentPluginsOriginalValue: number | null = null;
    currentManagingPlugin: PluginRecord | null = null;
    currentUpdateInfo: PluginBackendUpdateStatus | null = null;
    cardController: CardPageController | null = null;
    cardRenderer: PluginCardRenderer | null = null;
    viewMode: CollectionDisplayMode = resolveInitialCollectionDisplayMode(PLUGINS_VIEW_MODE_STORAGE_KEY);
    viewModeController: ViewModeController | null = null;

    constructor(catalogStore: CatalogStore) {
        this.catalogStore = catalogStore;
    }

    async refreshBackendUpdatePermissions(signal?: AbortSignal): Promise<void> {
        const token = this.#permissionToken.next();
        this.canAdministerPlugins = false;
        const permissions = await loadWebuiPermissionsSnapshot({ signal });
        if (!signal?.aborted && this.#permissionToken.isActive(token)) this.canAdministerPlugins = canManagePluginBackends(permissions);
    }

    backendUpdateAccess(plugin: PluginRecord): BackendUpdateAccess {
        const system = this.coreConfigCache?.['SYSTEM'];
        const runtime = isJsonObject(system) ? system['RUNTIME'] : null;
        return {
            canAdminister: this.canAdministerPlugins,
            online: isJsonObject(runtime) && runtime['STAY_OFFLINE'] === false,
            restartPending: getRestartState().required,
            catalogFresh: this.catalogStore.isFresh(),
            operationActive: requireTaskOperationsApi().getOperations({ pluginName: plugin.name }).length > 0
        };
    }

    clearTransientState(): void {
        this.#permissionToken.invalidate();
        this.canAdministerPlugins = false;
        this.recentItems.clear();
        this.progressMetadata.clear();
        this.activeToggles.clear();
        this.pendingToggleTargets.clear();
        this.deletingItems.clear();
        this.grouping.clear();
        this.coreConfigPromise = null;
        this.currentManagingPlugin = null;
        this.currentUpdateInfo = null;
    }
}

export { PluginsPageSession };
