/* SoAI - Models page runtime methods [frontend/assets/ts/pages/models/controllers/page/runtimeMethods.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isObject } from '@core/typeGuards.ts';
import type { ResourceIncomingObject, ResourceIncomingValue, ResourceItem } from '@core/data/ClientDataHub.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { getModelPlugin } from '@pages/models/controllers/modelsModelProperties.ts';
import { normalizeModelRecordStrict } from '@pages/models/controllers/page/state.ts';

const normalizeModelItems = (items: ReadonlyArray<ResourceItem>, context: string): ModelRecord[] => {
    const models: ModelRecord[] = [];
    for (const item of items) {
        models.push(normalizeModelRecordStrict(item, context));
    }
    return models;
};

const renderModelsItemsForRuntime = (dependencies: { getFilteredItems: () => ReadonlyArray<ResourceItem>; getAllItems: () => ReadonlyArray<ResourceItem>; syncAuthoritativeModelCount: (modelCount: number) => void; renderCollection: (payload: { filteredItems: ModelRecord[]; allItems: ModelRecord[] }) => void }): void => {
    const filteredItems = normalizeModelItems(dependencies.getFilteredItems(), 'ModelsPage.renderModelsItems.filtered');
    const allItems = normalizeModelItems(dependencies.getAllItems(), 'ModelsPage.renderModelsItems.all');
    dependencies.syncAuthoritativeModelCount(allItems.length);
    dependencies.renderCollection({ filteredItems, allItems });
};

const loadModelsPluginsForRuntime = async <
    TStore extends {
        ensureLoaded: (options?: { force?: boolean }) => Promise<ReadonlyArray<PluginRecord>>;
    }
>(
    dependencies: {
        catalogStore: TStore;
        collection: { getAll(): ResourceItem[] } | null;
        applyPluginSnapshot: (storeRef: TStore, options: { plugins: ReadonlyArray<PluginRecord>; reapply: boolean }) => void;
    },
    options: { force?: boolean } = {}
): Promise<PluginRecord[]> => {
    const ensureOptions = typeof options.force === 'boolean' ? { force: options.force } : undefined;
    const plugins = await dependencies.catalogStore.ensureLoaded(ensureOptions);
    const reapply = dependencies.collection ? dependencies.collection.getAll().length > 0 : false;
    dependencies.applyPluginSnapshot(dependencies.catalogStore, { plugins, reapply });
    return Array.from(plugins);
};

const cancelModelsDownloadForRuntime = (
    dependencies: {
        streams: { active: { has(key: string): boolean } };
        collectionRuntime: { cancelDownload(key: string): void };
        showNotification: (message: string, type: 'warning' | 'info') => void;
        updateDownloadBadge: () => void;
    },
    key: string
): void => {
    const active = dependencies.streams.active.has(key);
    dependencies.collectionRuntime.cancelDownload(key);
    dependencies.showNotification(i18n.t('models.notifications.downloadCancelled'), active ? 'warning' : 'info');
    dependencies.updateDownloadBadge();
};

const isResourceObject = (candidate: ResourceIncomingValue | null | undefined): candidate is ResourceIncomingObject => isObject(candidate);

const isValidModelItemForRuntime = (candidate: ResourceIncomingValue | null | undefined): boolean => {
    if (!isResourceObject(candidate)) return false;
    const id = candidate['universalId'] || candidate['id'] || candidate['name'];
    return Boolean(id && (getModelPlugin(candidate) || candidate['type'] === 'virtual'));
};

export { cancelModelsDownloadForRuntime, isValidModelItemForRuntime, loadModelsPluginsForRuntime, renderModelsItemsForRuntime };
