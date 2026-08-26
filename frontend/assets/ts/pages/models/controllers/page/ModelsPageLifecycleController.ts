/* SoAI - Models page load, refresh, shell, show, and hide lifecycle ownership [frontend/assets/ts/pages/models/controllers/page/ModelsPageLifecycleController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { handleModelsInitialAction, type ModelsInitialActionHost } from '@pages/models/controllers/modelsPageInitialActions.ts';
import type { ModelsLifecycleRuntimeDependencies } from '@pages/models/controllers/page/contracts.ts';
import { initializeModelsPageShell, loadModelsPageData } from '@pages/models/controllers/page/effects.ts';
import { refreshModelsPageRealtimeState, type ModelsRealtimeRefreshHost } from '@pages/models/controllers/page/realtimeRefreshController.ts';
import { initializeModelsViewMode, type ModelsViewModeHost } from '@pages/models/controllers/page/viewModeController.ts';

interface ModelsPageLifecycleDependencies {
    runtime: ModelsLifecycleRuntimeDependencies;
    cardController: { showLoading(): void; setDataInitialized(): void };
    initialActionHost: ModelsInitialActionHost;
    viewModeHost: ModelsViewModeHost;
    populateProviderFilter(): void;
    updateStats(): void;
}

class ModelsPageLifecycleController {
    readonly #dependencies: ModelsPageLifecycleDependencies;

    constructor(dependencies: ModelsPageLifecycleDependencies) {
        this.#dependencies = dependencies;
    }

    async loadData(parameters: JsonObject | undefined, context: { signal?: AbortSignal }, loadBaseData: (parameters: JsonObject | undefined, context: { signal?: AbortSignal }) => Promise<void>): Promise<void> {
        const { runtime } = this.#dependencies;
        await loadModelsPageData(
            {
                cardController: this.#dependencies.cardController,
                loadBaseData,
                collectionLifecycle: runtime.collection.collectionLifecycle,
                ensureCollectionStream: async (options) => {
                    await runtime.collection.collections.ensureStream(options);
                },
                catalogStore: runtime.session.catalogStore,
                ensureDataSubscriptions: () => runtime.infrastructure.streaming.ensureSubscriptions(),
                setupCatalogSubscription: () => runtime.catalog.setupSubscription(),
                populateProviderFilter: this.#dependencies.populateProviderFilter,
                updateStats: this.#dependencies.updateStats,
                beginRecentItemsSync: () => runtime.session.beginRecentItemsSync(),
                armRecentItems: (syncSequence) => runtime.session.armRecentItemsSync(syncSequence)
            },
            parameters,
            context
        );
    }

    initializeShell(): void {
        const { runtime } = this.#dependencies;
        const ui = initializeModelsPageShell(runtime.infrastructure);
        initializeModelsViewMode(this.#dependencies.viewModeHost, ui);
    }

    async refresh(parameters: JsonObject | null): Promise<void> {
        await refreshModelsPageRealtimeState(this.#realtimeHost());
        await handleModelsInitialAction(this.#dependencies.initialActionHost, parameters);
    }

    async show(): Promise<void> {
        const recentItemsSync = this.#dependencies.runtime.session.beginRecentItemsSync();
        await refreshModelsPageRealtimeState(this.#realtimeHost());
        this.#dependencies.runtime.session.armRecentItemsSync(recentItemsSync);
    }

    hide(): void {
        const { runtime } = this.#dependencies;
        runtime.session.clearRecentItems();
        if (runtime.collection.collections.runtime) runtime.collection.renderItems();
    }

    #realtimeHost(): ModelsRealtimeRefreshHost {
        const { runtime } = this.#dependencies;
        return {
            api: runtime.infrastructure.api,
            catalogStore: runtime.session.catalogStore,
            requireStreamManager: () => ({
                refresh: async (resource: string, options): Promise<JsonValue | null> => {
                    const refreshed = await runtime.infrastructure.streaming.runtime().resources.refresh(resource, options);
                    return isJsonValue(refreshed) ? refreshed : null;
                }
            }),
            ensureDataSubscriptions: () => runtime.infrastructure.streaming.ensureSubscriptions(),
            initializeCollectionView: runtime.collection.initializeCollectionView,
            reapplyCollection: (options?: { shouldRender?: boolean; updateStats?: boolean; updateFilters?: boolean }) => runtime.collection.collections.reapply(options)
        };
    }
}

export { ModelsPageLifecycleController };
