/* SoAI - Models page realtime refresh orchestration [frontend/assets/ts/pages/models/controllers/page/realtimeRefreshController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import type { EnsureCollectionStreamOptions } from '@core/routing/pages/pagetypes/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { CatalogStore } from '@features/catalog/public.ts';
import { refreshModelsPageRealtimeData } from '@pages/models/controllers/page/effects.ts';

interface ModelsRealtimeRefreshHost {
    api: ApiClient;
    catalogStore: CatalogStore;
    requireStreamManager: () => { refresh: (resource: string, options?: EnsureCollectionStreamOptions) => Promise<JsonValue | null> };
    ensureDataSubscriptions: () => Promise<void>;
    initializeCollectionView: () => void;
    reapplyCollection: (options?: { shouldRender?: boolean; updateStats?: boolean; updateFilters?: boolean }) => void;
}

const refreshModelsPageRealtimeState = async (host: ModelsRealtimeRefreshHost): Promise<void> => {
    await refreshModelsPageRealtimeData({
        refreshModelsCollection: async (): Promise<void> => {
            await host.requireStreamManager().refresh(MODELS, { allowDiscovery: true });
        },
        refreshPluginCatalog: async (): Promise<void> => {
            await host.catalogStore.refresh();
        },
        ensureDataSubscriptions: async (): Promise<void> => {
            await host.ensureDataSubscriptions();
        },
        reapplyCollection: (options): void => {
            host.initializeCollectionView();
            host.reapplyCollection(options);
        }
    });
};

export { refreshModelsPageRealtimeState };
export type { ModelsRealtimeRefreshHost };
