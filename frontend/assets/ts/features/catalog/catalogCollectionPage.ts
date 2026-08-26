/* SoAI - Catalog feature collection page [frontend/assets/ts/features/catalog/catalogCollectionPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction } from '@core/typeGuards.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { subscribeCollectionWithCatalog, type CatalogStore, type CatalogSubscriptionManager } from '@features/catalog/catalogSubscriptionManager.ts';

interface SetupOptions<C> {
    manager: CatalogSubscriptionManager;
    applySnapshot: (store: CatalogStore, plugins: ReadonlyArray<PluginRecord>, options: { reapply: boolean }) => void;
    getCollection: (store: CatalogStore) => C;
    reapplyCollection: () => void;
    reapplyOnInitialize?: boolean | undefined;
}

export const setupCatalogBackedCollection = <C>({ manager, applySnapshot, getCollection, reapplyCollection, reapplyOnInitialize = true }: SetupOptions<C>): void => {
    if (!manager || !isFunction(manager.subscribeToCatalog) || !isFunction(manager.subscribeToCapabilityManifest) || !isFunction(manager.requireStore)) {
        throw new Error('Catalog-backed collection requires a catalog subscription manager');
    }
    if (!isFunction(applySnapshot)) throw new Error('Catalog-backed collection requires a snapshot handler');
    if (!isFunction(getCollection)) throw new Error('Catalog-backed collection requires a collection resolver');
    if (!isFunction(reapplyCollection)) throw new Error('Catalog-backed collection requires a reapply handler');

    const reapply = (): void => reapplyCollection();
    const apply = (store: CatalogStore, plugins: ReadonlyArray<PluginRecord>, { reapplyCollection: shouldReapply }: { reapplyCollection: boolean }): void => {
        applySnapshot(store, plugins, { reapply: shouldReapply });
    };

    subscribeCollectionWithCatalog({
        manager,
        onCatalogChange: (store: CatalogStore, plugins: ReadonlyArray<PluginRecord>) => apply(store, plugins, { reapplyCollection: true }),
        onCatalogInitialize: (store: CatalogStore) => apply(store, store.getPlugins(), { reapplyCollection: reapplyOnInitialize }),
        getCollection: (store: CatalogStore) => getCollection(store),
        reapplyCollection: (store: CatalogStore) => {
            const collection = getCollection(store);
            if (!collection) return;
            reapply();
        }
    });
};
