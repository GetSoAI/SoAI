/* SoAI - Models plugin catalog state and subscription ownership [frontend/assets/ts/pages/models/controllers/page/ModelsPluginCatalogController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageCollections } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { createCatalogSubscriptionManager, type CatalogStore } from '@features/catalog/public.ts';
import { applyPluginSnapshot, refreshPluginCaches, setupCatalogSubscription } from '@pages/models/controllers/page/effects.ts';
import type { ModelsPageSession } from '@pages/models/controllers/page/ModelsPageSession.ts';
import { loadModelsPluginsForRuntime } from '@pages/models/controllers/page/runtimeMethods.ts';

interface ModelsPluginCatalogUi {
    updateProviderButtonVisibility(): void;
    updateVirtualModelsButtonVisibility(): void;
}

class ModelsPluginCatalogController {
    readonly #session: ModelsPageSession;
    readonly #collections: PageCollections;
    readonly subscriptions: ReturnType<typeof createCatalogSubscriptionManager>;
    #ui: ModelsPluginCatalogUi | null = null;

    constructor(session: ModelsPageSession, collections: PageCollections) {
        this.#session = session;
        this.#collections = collections;
        this.subscriptions = createCatalogSubscriptionManager({ getStore: () => session.catalogStore, requireMessage: 'Models page requires an initialized catalog store' });
    }

    attachUi(ui: ModelsPluginCatalogUi): void {
        this.#ui = ui;
    }

    refresh(plugins?: ReadonlyArray<PluginRecord> | null): void {
        refreshPluginCaches(this.#session, this.#session.catalogStore, plugins ?? null);
    }

    apply(store: CatalogStore, options: { plugins?: ReadonlyArray<PluginRecord> | null; updateUI?: boolean; reapply?: boolean } = {}): void {
        const updateUI = options.updateUI !== false;
        if (updateUI && !this.#ui) throw new Error('Models plugin catalog UI is not attached');
        applyPluginSnapshot(
            this.#session,
            store,
            {
                updateProviderButtonVisibility: () => this.#requireUi().updateProviderButtonVisibility(),
                updateVirtualModelsButtonVisibility: () => this.#requireUi().updateVirtualModelsButtonVisibility()
            },
            options,
            (reapplyOptions) => this.#collections.reapply(reapplyOptions)
        );
    }

    setupSubscription(): void {
        setupCatalogSubscription({
            catalogSubscriptions: this.subscriptions,
            collection: this.#collections.runtime,
            reapplyCollection: (options) => this.#collections.reapply(options),
            applyPluginSnapshot: (store, options) => this.apply(store, options)
        });
    }

    async load(options: { force?: boolean } = {}): Promise<PluginRecord[]> {
        return await loadModelsPluginsForRuntime(
            {
                catalogStore: this.#session.catalogStore,
                collection: this.#collections.runtime,
                applyPluginSnapshot: (store, snapshotOptions) => this.apply(store, snapshotOptions)
            },
            options
        );
    }

    cleanup(): void {
        this.subscriptions.cleanup();
        this.#ui = null;
    }

    #requireUi(): ModelsPluginCatalogUi {
        if (!this.#ui) throw new Error('Models plugin catalog UI is not attached');
        return this.#ui;
    }
}

export { ModelsPluginCatalogController };
