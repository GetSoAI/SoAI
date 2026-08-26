/* SoAI - Search feature panel service [frontend/assets/ts/features/search/panel/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dispatchCustomEvent } from '@core/environment/public.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import type { SearchIndex, SearchItem, SearchOptions } from '@core/search/searchTypes.ts';
import { parseSearchDirectReference } from '@core/search/directReference.ts';
import { combineSearchResults, getSearchLocalResults, searchCatalog } from '@features/search/panel/actions.ts';
import { ensureApiReady, hydrateIndexFromResources, markSystemReady, monitorSystemReadiness, primeDataResources, subscribeToDataStreams, waitForSystemReady } from '@features/search/panel/effects.ts';
import { createSearchExecutionContext } from '@features/search/panel/executionContext.ts';
import { resolveSoaiPathFileResult, searchFileExplorerResults, type FileSearchContext } from '@features/search/panel/fileResults.ts';
import { getSearchIndexBucket } from '@features/search/panel/mappers.ts';
import { loadSearchGrantedActions } from '@features/search/panel/permissions.ts';
import { buildPageIndexEntries } from '@features/search/searchPageIndex.ts';
import { refreshStaticSearchIndexes } from '@features/search/panel/staticIndexes.ts';
import type { SearchBackendDependencies, SearchIndexKey } from '@features/search/panel/contracts.ts';
import { SearchBackendState } from '@features/search/panel/state.ts';

class SearchBackend {
    #dependencies: SearchBackendDependencies;
    #state: SearchBackendState;
    readonly #permissionRefreshToken = new SequenceToken();
    readonly #staticRefreshToken = new SequenceToken();

    constructor(dependencies: SearchBackendDependencies) {
        this.#dependencies = dependencies;
        this.#state = new SearchBackendState();
    }

    get state(): SearchBackendState {
        return this.#state;
    }

    get apiClient(): SearchBackendDependencies['apiClient'] {
        return this.#dependencies.apiClient;
    }

    reset(): void {
        this.#permissionRefreshToken.invalidate();
        this.#staticRefreshToken.invalidate();
        this.#state.reset();
    }

    resetStreamSubscriptions(): void {
        this.#state.resetStreamSubscriptions();
    }

    isSystemReady(): boolean {
        return this.#state.isSystemReady();
    }

    ensureSearchIndex(): SearchIndex {
        return this.#state.ensureSearchIndex();
    }

    indexPages(): void {
        const index = this.ensureSearchIndex();
        const pageMap = index.pages || (index.pages = new Map());
        pageMap.clear();
        buildPageIndexEntries(this.#state.grantedActions).forEach((page) => pageMap.set(page.id, page));
        this.#state.pagesIndexed = true;
        this.#dependencies.onIndexUpdated('pages', pageMap.size);
    }

    async refreshStaticIndexes(): Promise<void> {
        const sequence = this.#staticRefreshToken.next();
        await refreshStaticSearchIndexes({
            dependencies: this.#dependencies,
            state: this.#state,
            updateSearchIndex: (type, items) => {
                if (this.#staticRefreshToken.isActive(sequence)) {
                    this.updateSearchIndex(type, items);
                }
            }
        });
    }

    async refreshGrantedActions(): Promise<boolean> {
        const sequence = this.#permissionRefreshToken.next();
        const actions = await loadSearchGrantedActions();
        if (!this.#permissionRefreshToken.isActive(sequence)) {
            return false;
        }
        this.#state.grantedActions = actions;
        this.#state.invalidateSearches();
        this.syncAccessControlledIndexes();
        return true;
    }

    resetGrantedActions(): void {
        this.#permissionRefreshToken.invalidate();
        this.#staticRefreshToken.invalidate();
        this.#state.invalidateSearches();
        this.#state.grantedActions = new Set();
        this.syncAccessControlledIndexes();
        const index = this.ensureSearchIndex();
        index.configs.clear();
        index.help.clear();
        index.modals.clear();
        index.powerActions.clear();
        this.indexPages();
    }

    syncAccessControlledIndexes(): void {
        const index = this.ensureSearchIndex();
        const actions = this.#state.grantedActions;
        if (!actions.has('MODEL_READ')) {
            index.models.clear();
        }
        if (!actions.has('PLUGIN_READ')) {
            index.plugins.clear();
        }
        if (!actions.has('HARDWARE_READ')) {
            index.devices.clear();
        }
        if (!actions.has('FILE_EXPLORER_READ')) {
            index.pages.delete('fileExplorer');
        }
        this.clearCache();
    }

    refreshIndexFromResources(): void {
        this.hydrateIndexFromResources();
        this.broadcastIndexCounts();
    }

    broadcastIndexCounts(): void {
        const index = this.ensureSearchIndex();
        this.#dependencies.onIndexUpdated('models', index.models.size);
        this.#dependencies.onIndexUpdated('plugins', index.plugins.size);
        this.#dependencies.onIndexUpdated('devices', index.devices.size);
        this.#dependencies.onIndexUpdated('pages', index.pages.size);
        this.#dependencies.onIndexUpdated('configs', index.configs.size);
        this.#dependencies.onIndexUpdated('help', index.help.size);
        this.#dependencies.onIndexUpdated('modals', index.modals.size);
        this.#dependencies.onIndexUpdated('powerActions', index.powerActions.size);
    }

    loadRecentSearches(): void {
        this.#state.setRecentSearches(this.#dependencies.storage.getRecentSearches?.() ?? []);
        this.#dependencies.onMeta('recent-searches', this.#state.getRecentSearches().length);
    }

    clearRecentSearches(): void {
        this.#dependencies.storage.clearRecentSearches?.();
        this.#state.setRecentSearches([]);
        this.#dependencies.onMeta('recent-searches', 0);
    }

    cleanupExpiredCache(): void {
        this.#state.cleanupExpiredCache();
    }

    clearCache(): void {
        this.#state.clearCache();
    }

    clearCacheForType(type: SearchIndexKey): void {
        this.#state.clearCacheForType(type);
    }

    searchLocalIndex(term: string): SearchItem[] {
        return getSearchLocalResults(
            {
                dependencies: { apiClient: this.#dependencies.apiClient },
                onSearchResults: () => {},
                ensureApiReady: () => this.ensureApiReady(),
                primeDataResources: () => this.primeDataResources(),
                waitForSystemReady: (timeout: number) => this.waitForSystemReady(timeout),
                state: this.#state
            },
            term
        );
    }

    combineResults(remoteResults: SearchItem[], localResults: SearchItem[], limit: number): SearchItem[] {
        return combineSearchResults(remoteResults, localResults, limit);
    }

    async search(query: string, limitOrOptions: number | SearchOptions = 10, options: SearchOptions = {}): Promise<SearchItem[]> {
        if (parseSearchDirectReference(query)?.kind === 'soaiPath') {
            return [];
        }
        return await searchCatalog(createSearchExecutionContext(this), query, limitOrOptions, options);
    }

    async searchFiles(query: string, limit: number = 10, options: SearchOptions = {}): Promise<SearchItem[]> {
        if (!this.#state.grantedActions.has('FILE_EXPLORER_READ')) {
            return [];
        }
        const context = { apiClient: this.#dependencies.apiClient };
        const directReference = parseSearchDirectReference(query);
        if (directReference !== null && directReference.kind === 'soaiPath') {
            return await this.#resolveSoaiPathReference(context, directReference.virtualPath, options);
        }
        return await searchFileExplorerResults(context, query, limit, options);
    }

    async #resolveSoaiPathReference(context: FileSearchContext, virtualPath: string, options: SearchOptions): Promise<SearchItem[]> {
        const generation = this.#state.getSearchGeneration();
        const results = await resolveSoaiPathFileResult(context, virtualPath, options);
        if (!this.#state.isSearchGenerationActive(generation)) {
            return [];
        }
        return results;
    }

    async ensureApiReady(): Promise<void> {
        const generation = this.#state.getRuntimeGeneration();
        await ensureApiReady({
            dependencies: this.#dependencies,
            state: this.#state,
            isActive: () => this.#state.isRuntimeGenerationActive(generation),
            onSystemReady: () => this.markSystemReady()
        });
    }

    async monitorSystemReadiness(): Promise<void> {
        const generation = this.#state.getRuntimeGeneration();
        await monitorSystemReadiness({
            dependencies: this.#dependencies,
            state: this.#state,
            isActive: () => this.#state.isRuntimeGenerationActive(generation),
            onSystemReady: () => this.markSystemReady()
        });
    }

    private markSystemReady(): void {
        markSystemReady({
            dependencies: this.#dependencies,
            state: this.#state,
            isActive: () => true,
            onSystemReady: () => dispatchCustomEvent('soai:search:ready', {})
        });
    }

    async waitForSystemReady(timeout: number = 3000): Promise<boolean> {
        const generation = this.#state.getRuntimeGeneration();
        return await waitForSystemReady(
            {
                dependencies: this.#dependencies,
                state: this.#state,
                isActive: () => this.#state.isRuntimeGenerationActive(generation),
                onSystemReady: () => this.markSystemReady()
            },
            timeout
        );
    }

    async primeDataResources(): Promise<void> {
        const generation = this.#state.getRuntimeGeneration();
        await primeDataResources({
            dependencies: this.#dependencies,
            state: this.#state,
            isActive: () => this.#state.isRuntimeGenerationActive(generation),
            updateSearchIndex: (type, items) => this.updateSearchIndex(type, items)
        });
    }

    async subscribeToDataStreams(): Promise<void> {
        const generation = this.#state.getRuntimeGeneration();
        await subscribeToDataStreams({
            dependencies: this.#dependencies,
            state: this.#state,
            isActive: () => this.#state.isRuntimeGenerationActive(generation),
            updateSearchIndex: (type, items) => this.updateSearchIndex(type, items)
        });
    }

    hydrateIndexFromResources(): void {
        const generation = this.#state.getRuntimeGeneration();
        hydrateIndexFromResources({
            dependencies: this.#dependencies,
            state: this.#state,
            isActive: () => this.#state.isRuntimeGenerationActive(generation),
            updateSearchIndex: (type, items) => this.updateSearchIndex(type, items)
        });
    }

    canIndexType(type: SearchIndexKey): boolean {
        const actions = this.#state.grantedActions;
        if (type === 'models') {
            return actions.has('MODEL_READ');
        }
        if (type === 'plugins') {
            return actions.has('PLUGIN_READ');
        }
        if (type === 'devices') {
            return actions.has('HARDWARE_READ');
        }
        return true;
    }

    updateSearchIndex(type: SearchIndexKey, items: SearchItem[]): void {
        if (!this.canIndexType(type)) {
            this.clearCacheForType(type);
            this.#dependencies.onIndexUpdated(type, 0);
            return;
        }
        const index = this.ensureSearchIndex();
        const bucket = getSearchIndexBucket(index, type);
        bucket.clear();
        for (const item of items) {
            if (item && item.id) {
                bucket.set(item.id, item);
            }
        }
        this.clearCacheForType(type);
        this.#dependencies.onIndexUpdated(type, bucket.size);
    }

    searchResultsDispatched(query: string, results: SearchItem[]): void {
        this.#dependencies.onSearchResults(query, results);
    }
}

export { SearchBackend };
export type { SearchBackendDependencies };
