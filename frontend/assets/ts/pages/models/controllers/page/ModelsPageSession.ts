/* SoAI - Models page domain state ownership [frontend/assets/ts/pages/models/controllers/page/ModelsPageSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CollectionGroupingState } from '@core/collectionpage/collectionGroupingState.ts';
import { createRecentItemTracker } from '@core/collectionpage/recentItemTracker.ts';
import type { ResourceSnapshot } from '@core/data/ClientDataHub.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { parseEpochMsOrNull } from '@core/time/epochMs.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { resolveInitialCollectionDisplayMode, type CollectionDisplayMode, type ViewModeController } from '@core/uiprimitives/viewmode/public.ts';
import type { CatalogStore } from '@features/catalog/public.ts';
import type { InitialActionContext } from '@pages/models/controllers/page/clickDispatch.ts';
import { resolveModelsItemCardId } from '@pages/models/controllers/modelsModelProperties.ts';
import { normalizeModelRecordStrict } from '@pages/models/controllers/page/state.ts';
import type { CardPageController } from '@core/routing/pages/collections/cardgridpage/public.ts';
import type { ModelCardRenderer } from '@pages/models/rendering/CardRenderer.ts';

const MODELS_VIEW_MODE_STORAGE_KEY = 'soai.models.viewMode';

class ModelsPageSession {
    readonly catalogStore: CatalogStore;
    readonly recentItems = createRecentItemTracker();
    readonly availablePlugins: PluginRecord[] = [];
    readonly allPlugins: PluginRecord[] = [];
    readonly providerPlugins: PluginRecord[] = [];
    readonly downloadPlugins: PluginRecord[] = [];
    readonly pluginLookup = new Map<string, PluginRecord>();
    readonly grouping = new CollectionGroupingState<ModelRecord>();
    readonly deletingItems = new Set<string>();
    initialActionContext: InitialActionContext | null = null;
    currentMetrics: JsonObject | null = null;
    metricsPresentationSignature: string | null = null;
    viewMode: CollectionDisplayMode = resolveInitialCollectionDisplayMode(MODELS_VIEW_MODE_STORAGE_KEY);
    viewModeController: ViewModeController | null = null;
    cardRenderer: ModelCardRenderer | null = null;
    cardController: CardPageController | null = null;
    #recentItemsBoundaryMs: number | null = null;

    constructor(catalogStore: CatalogStore) {
        this.catalogStore = catalogStore;
    }

    beginRecentItemsSync(): number {
        return this.recentItems.beginSync();
    }

    armRecentItemsSync(sequence: number): void {
        const boundaryMs = serverEpochMs();
        if (this.recentItems.armSync(sequence)) {
            this.#recentItemsBoundaryMs = boundaryMs;
        }
    }

    consumeModelsSnapshot(snapshot: ResourceSnapshot): void {
        const modelsByIdentifier = new Map<string, ModelRecord>();
        const orphanedIdentifiers: string[] = [];
        for (const item of snapshot.items) {
            const model = normalizeModelRecordStrict(item, 'ModelsPageSession.consumeModelsSnapshot');
            const identifier = resolveModelsItemCardId(model);
            if (!identifier) {
                continue;
            }
            modelsByIdentifier.set(identifier, model);
            if (model.isOrphaned === true) {
                orphanedIdentifiers.push(identifier);
            }
        }
        this.recentItems.unmarkMany(orphanedIdentifiers);
        const boundaryMs = this.#recentItemsBoundaryMs;
        const value = toJsonCompatibleValue(snapshot);
        this.recentItems.consumeSnapshot(isJsonObject(value) ? value : null, (identifier) => {
            const model = modelsByIdentifier.get(identifier);
            if (!model || model.isOrphaned === true || boundaryMs === null) {
                return false;
            }
            const createdAtMs = parseEpochMsOrNull(model.createdAtMs);
            return createdAtMs !== null && createdAtMs >= boundaryMs;
        });
    }

    clearRecentItems(): void {
        this.#recentItemsBoundaryMs = null;
        this.recentItems.clear();
    }

    clear(): void {
        this.clearRecentItems();
        this.availablePlugins.length = 0;
        this.allPlugins.length = 0;
        this.providerPlugins.length = 0;
        this.downloadPlugins.length = 0;
        this.pluginLookup.clear();
        this.grouping.clear();
        this.deletingItems.clear();
        this.initialActionContext = null;
        this.currentMetrics = null;
        this.metricsPresentationSignature = null;
    }
}

export { ModelsPageSession };
