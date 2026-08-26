/* SoAI - Routed page collection configuration, rendering, and cleanup ownership [frontend/assets/ts/core/routing/pages/basepagecollections/PageCollections.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { err, request } from '@core/routing/pages/basepagecore/actions.ts';
import { getCollectionConfiguration, getCollectionKey, hasCollectionConfiguration, setCollectionConfiguration } from '@core/routing/pages/basepagecollections/actions.ts';
import type { PageCollectionBehavior, PageCollectionsDependencies } from '@core/routing/pages/basepagecollections/contracts.ts';
import { cleanupCollectionState, getCollectionRuntime, getCollectionTargets } from '@core/routing/pages/basepagecollections/dom.ts';
import { ensureCollectionStream, initializeStandardCollection, reapplyCollection, toggleEmptyState } from '@core/routing/pages/basepagecollections/effects.ts';
import { createBasePageCollectionsState, type BasePageCollectionsState } from '@core/routing/pages/basepagecollections/state.ts';
import type { CollectionConfigurationOptions, CollectionRuntime, CollectionTargets, EnsureCollectionStreamOptions, ReapplyCollectionOptions } from '@core/routing/pages/pagetypes/public.ts';

interface PageCollectionsContract {
    readonly runtime: CollectionRuntime | null;
    readonly view: BasePageCollectionsState['collectionView'];
    initialize(config: CollectionConfigurationOptions): void;
    hasConfiguration(): boolean;
    configuration(): CollectionConfigurationOptions | null;
    key(): string;
    ensureStream(options?: EnsureCollectionStreamOptions): Promise<string>;
    toggleEmptyState(showEmpty: boolean): void;
    reapply(options?: ReapplyCollectionOptions): void;
    targets(): CollectionTargets | null;
    cleanupState(): void;
}

class PageCollections implements PageCollectionsContract {
    readonly #dependencies: PageCollectionsDependencies;
    readonly #behavior: PageCollectionBehavior;
    readonly #state: BasePageCollectionsState;

    constructor(dependencies: PageCollectionsDependencies, behavior: PageCollectionBehavior) {
        this.#dependencies = dependencies;
        this.#behavior = behavior;
        this.#state = createBasePageCollectionsState();
    }

    get runtime(): CollectionRuntime | null {
        return getCollectionRuntime(this.#state);
    }

    set runtime(value: CollectionRuntime | null) {
        this.#state.collection = value;
    }

    get view(): BasePageCollectionsState['collectionView'] {
        return this.#state.collectionView;
    }

    initialize(config: CollectionConfigurationOptions): void {
        if (!config.collectionKey) throw err('Collection key required');
        setCollectionConfiguration(this.#state, this.#dependencies.pageId, { ...config, collectionKey: request(config.collectionKey, 'collection key') });
        initializeStandardCollection(this.#dependencies, this.#behavior, this.#state, config);
    }

    hasConfiguration(): boolean {
        return hasCollectionConfiguration(this.#state);
    }

    configuration(): CollectionConfigurationOptions | null {
        return getCollectionConfiguration(this.#state);
    }

    key(): string {
        return getCollectionKey(this.#state);
    }

    async ensureStream(options: EnsureCollectionStreamOptions = {}): Promise<string> {
        return ensureCollectionStream(this.#dependencies, this.#state, options);
    }

    toggleEmptyState(showEmpty: boolean): void {
        toggleEmptyState(this.#dependencies, this.#state, showEmpty);
    }

    reapply(options: ReapplyCollectionOptions = {}): void {
        reapplyCollection(this.#dependencies, this.#behavior, this.#state, options);
    }

    targets(): CollectionTargets | null {
        return getCollectionTargets(this.#state, (selector) => this.#dependencies.pageDom.get(selector));
    }

    cleanupState(): void {
        cleanupCollectionState(this.#state);
    }
}

export { PageCollections };
export type { PageCollectionsContract };
export interface PageCollectionsHost {
    collections: PageCollectionsContract;
}
