/* SoAI - Plugins page domain state ownership [frontend/assets/ts/pages/plugins/controllers/page/PluginsPageSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createRecentItemTracker, type RecentItemTracker } from '@core/collectionpage/recentItemTracker.ts';
import type { CardPageController } from '@core/routing/pages/collections/cardgridpage/public.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { resolveInitialCollectionDisplayMode, type CollectionDisplayMode, type ViewModeController } from '@core/uiprimitives/viewmode/public.ts';
import type { CatalogStore } from '@features/catalog/public.ts';
import type { PluginCardRenderer } from '@pages/plugins/rendering/cardrenderer/service.ts';
import type { PluginBackendUpdateStatus } from '@core/api/contracts/pluginManagementContracts.ts';
import { CollectionGroupingState } from '@core/collectionpage/collectionGroupingState.ts';

const PLUGINS_VIEW_MODE_STORAGE_KEY = 'soai.plugins.viewMode';

class PluginsPageSession {
    readonly catalogStore: CatalogStore;
    readonly recentItems: RecentItemTracker = createRecentItemTracker();
    readonly progressMetadata = new Map<string, JsonObject>();
    readonly activeToggles = new Set<string>();
    readonly pendingToggleTargets = new Map<string, boolean>();
    readonly deletingItems = new Set<string>();
    readonly grouping = new CollectionGroupingState<PluginRecord>();
    coreConfigCache: JsonObject | null = null;
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

    clearTransientState(): void {
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
