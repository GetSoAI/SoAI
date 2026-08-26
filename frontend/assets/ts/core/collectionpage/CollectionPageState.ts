/* SoAI - Collection page view and shell initialization state ownership [frontend/assets/ts/core/collectionpage/CollectionPageState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageCollections } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { CollectionPageLifecycle } from '@core/routing/pages/collections/pagelifecyclemanager/public.ts';
import type { CollectionConfigurationOptions, CollectionOptionsInternal } from '@core/routing/pages/pagetypes/public.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { updateCollectionFilterState } from '@core/collectionpage/filterState.ts';

interface CollectionPageStateConfig {
    pageId: string;
    collectionKey: string;
    collectionOptions: CollectionOptionsInternal;
    defaultSort: string;
}

class CollectionPageState {
    readonly #config: CollectionPageStateConfig;
    #viewInitialized = false;
    #shellInitialized = false;
    searchQuery = '';
    filterProvider = 'all';
    filterStatus = 'all';
    sortBy: string | null;
    sortOrder: 'asc' | 'desc' | null = 'asc';

    constructor(config: CollectionPageStateConfig) {
        this.#config = config;
        this.sortBy = config.defaultSort || 'name';
    }

    getFilterProvider(): string {
        return this.filterProvider;
    }

    setFilterProvider(value: string): void {
        this.filterProvider = value;
    }

    getFilterStatus(): string {
        return this.filterStatus;
    }

    setFilterStatus(value: string): void {
        this.filterStatus = value;
    }

    getSortBy(): string | null {
        return this.sortBy;
    }

    setSortBy(value: string | null): void {
        this.sortBy = value;
    }

    getSortOrder(): 'asc' | 'desc' | null {
        return this.sortOrder;
    }

    setSortOrder(value: 'asc' | 'desc' | null): void {
        this.sortOrder = value;
    }

    getSearchQuery(): string {
        return this.searchQuery;
    }

    setSearchQuery(value: string): void {
        this.searchQuery = value;
    }

    initializeView(collections: PageCollections, overrides: Partial<CollectionConfigurationOptions>): void {
        if (this.#viewInitialized && collections.view) return;
        collections.initialize({ collectionKey: this.#config.collectionKey, collectionOptions: this.#config.collectionOptions, ...overrides });
        if (!this.sortBy) this.sortBy = this.#config.defaultSort;
        this.#viewInitialized = true;
    }

    setFilterValue(property: string, value: string): void {
        updateCollectionFilterState(this.#config.pageId, property, value, {
            setProvider: (next) => {
                this.filterProvider = next;
            },
            setStatus: (next) => {
                this.filterStatus = next;
            }
        });
    }

    async initializeShell(lifecycle: CollectionPageLifecycle, parameters: JsonObject | null | undefined, onReady: (parameters: JsonObject | null | undefined, layout: { grid: HTMLElement; emptyState: HTMLElement | null }) => Promise<void>, options: { signal?: AbortSignal } = {}): Promise<void> {
        if (this.#shellInitialized) return;
        await lifecycle.initializeShell(async (layout) => onReady(parameters, layout), options);
        this.#shellInitialized = true;
    }

    reset(): void {
        this.#viewInitialized = false;
        this.#shellInitialized = false;
    }
}

export { CollectionPageState };
export type { CollectionPageStateConfig };
