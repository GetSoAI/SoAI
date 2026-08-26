/* SoAI - Prompts collection filter state and lifecycle controls [frontend/assets/ts/pages/prompts/controllers/page/PromptsCollectionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionCompositionBehavior } from '@core/collectionpage/composeCollectionRuntime.ts';
import type { CollectionPageState } from '@core/collectionpage/CollectionPageState.ts';
import { getCollectionFilter } from '@core/routing/pages/basepagecollections/mappers.ts';
import type { ResourceItem } from '@core/data/ClientDataHub.ts';

class PromptsCollectionController {
    readonly #state: CollectionPageState;
    readonly #pageLifecycle: { readonly isDestroyed: boolean };
    readonly #behavior: Pick<CollectionCompositionBehavior, 'getItemSearchFields' | 'applyCustomFilters'>;

    constructor(state: CollectionPageState, pageLifecycle: { readonly isDestroyed: boolean }, behavior: Pick<CollectionCompositionBehavior, 'getItemSearchFields' | 'applyCustomFilters'>) {
        this.#state = state;
        this.#pageLifecycle = pageLifecycle;
        this.#behavior = behavior;
    }

    getSortBy(): string | null {
        return this.#state.sortBy;
    }

    setSortBy(value: string): void {
        this.#state.sortBy = value;
    }

    getSortOrder(): 'asc' | 'desc' | null {
        return this.#state.sortOrder;
    }

    setSortOrder(value: 'asc' | 'desc' | null): void {
        this.#state.sortOrder = value;
    }

    getSearchQuery(): string {
        return this.#state.searchQuery;
    }

    setSearchQuery(value: string): void {
        this.#state.searchQuery = value;
    }

    isDestroyed(): boolean {
        return this.#pageLifecycle.isDestroyed;
    }

    getCollectionFilter(): (item: ResourceItem) => boolean {
        return getCollectionFilter({
            searchQuery: this.#state.searchQuery,
            filterProvider: this.#state.filterProvider,
            filterStatus: this.#state.filterStatus,
            getItemSearchFields: this.#behavior.getItemSearchFields,
            applyCustomFilters: this.#behavior.applyCustomFilters
        });
    }
}

export { PromptsCollectionController };
