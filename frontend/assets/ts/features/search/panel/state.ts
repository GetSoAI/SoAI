/* SoAI - Search feature panel state [frontend/assets/ts/features/search/panel/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import type { CachedSearch, SearchIndex } from '@core/search/searchTypes.ts';
import { isArray } from '@core/typeGuards.ts';
import type { SearchIndexKey } from '@features/search/panel/contracts.ts';

const SEARCH_CACHE_TTL_MS = 3e5;

const searchItemMatchesIndexType = (entry: { type: string; category: string }, type: SearchIndexKey): boolean => {
    if (entry.type === type || entry.category === type) {
        return true;
    }
    if (type === 'pages') {
        return entry.type === 'page' || entry.category === 'page';
    }
    if (type === 'devices') {
        return entry.type === 'device' || entry.category === 'hardware';
    }
    if (type === 'configs') {
        return entry.type === 'config' || entry.category === 'config' || entry.type === 'configuration' || entry.category === 'configuration';
    }
    if (type === 'help') {
        return entry.type === 'help' || entry.category === 'help';
    }
    if (type === 'modals') {
        return entry.type === 'modal' || entry.category === 'modal' || entry.type === 'modals' || entry.category === 'modals';
    }
    if (type === 'powerActions') {
        return entry.type === 'power-actions' || entry.category === 'power-actions';
    }
    return false;
};

class SearchBackendState {
    searchCache: Map<string, CachedSearch>;
    cacheTimeout: number;
    pendingRemoteSearches: Map<string, Promise<void>>;
    systemReady: boolean;
    systemReadyPromise: Promise<void> | null;
    collectionsPrimedPromise: Promise<void> | null;
    searchIndex: SearchIndex | null;
    recentSearches: string[];
    grantedActions: ReadonlySet<string>;
    pagesIndexed: boolean;
    streamSubscriptionsRegistered: boolean;
    streamSubscriptionTask: Promise<void> | null;
    readonly #searchGeneration: SequenceToken;
    readonly #runtimeGeneration: SequenceToken;

    constructor() {
        this.searchCache = new Map();
        this.cacheTimeout = SEARCH_CACHE_TTL_MS;
        this.pendingRemoteSearches = new Map();
        this.systemReady = false;
        this.systemReadyPromise = null;
        this.collectionsPrimedPromise = null;
        this.searchIndex = null;
        this.recentSearches = [];
        this.grantedActions = new Set();
        this.pagesIndexed = false;
        this.streamSubscriptionsRegistered = false;
        this.streamSubscriptionTask = null;
        this.#searchGeneration = new SequenceToken();
        this.#runtimeGeneration = new SequenceToken();
    }

    reset(): void {
        this.searchCache = new Map();
        this.pendingRemoteSearches.clear();
        this.searchIndex = null;
        this.recentSearches = [];
        this.grantedActions = new Set();
        this.#searchGeneration.invalidate();
        this.#runtimeGeneration.invalidate();
        this.systemReady = false;
        this.systemReadyPromise = null;
        this.collectionsPrimedPromise = null;
        this.pagesIndexed = false;
        this.streamSubscriptionsRegistered = false;
        this.streamSubscriptionTask = null;
    }

    resetStreamSubscriptions(): void {
        this.streamSubscriptionsRegistered = false;
        this.streamSubscriptionTask = null;
    }

    isSystemReady(): boolean {
        return this.systemReady;
    }

    getRuntimeGeneration(): number {
        return this.#runtimeGeneration.value;
    }

    isRuntimeGenerationActive(generation: number): boolean {
        return this.#runtimeGeneration.isActive(generation);
    }

    ensureSearchIndex(): SearchIndex {
        if (!this.searchIndex) {
            this.searchIndex = {
                models: new Map(),
                plugins: new Map(),
                devices: new Map(),
                configs: new Map(),
                pages: new Map(),
                help: new Map(),
                modals: new Map(),
                powerActions: new Map()
            };
        }
        return this.searchIndex;
    }

    setRecentSearches(recentSearches: string[]): void {
        this.recentSearches = isArray(recentSearches) ? recentSearches : [];
    }

    getRecentSearches(): string[] {
        return this.recentSearches;
    }

    clearCache(): void {
        this.searchCache.clear();
    }

    getSearchGeneration(): number {
        return this.#searchGeneration.value;
    }

    isSearchGenerationActive(generation: number): boolean {
        return this.#searchGeneration.isActive(generation);
    }

    invalidateSearches(): void {
        this.#searchGeneration.invalidate();
        this.searchCache.clear();
        this.pendingRemoteSearches.clear();
    }

    clearCacheForType(type: SearchIndexKey): void {
        for (const [key, cached] of this.searchCache.entries()) {
            if (cached && isArray(cached.results) && cached.results.some((entry) => searchItemMatchesIndexType(entry, type))) {
                this.searchCache.delete(key);
            }
        }
    }

    cleanupExpiredCache(): void {
        for (const [key, cached] of this.searchCache.entries()) {
            if (Date.now() - cached.timestamp > this.cacheTimeout) {
                this.searchCache.delete(key);
            }
        }
    }
}

export { SearchBackendState };
