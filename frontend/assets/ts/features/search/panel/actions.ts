/* SoAI - Search feature panel actions [frontend/assets/ts/features/search/panel/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { handleApiResult } from '@core/api/apiResultHandler.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createSearchCacheKey, normalizeSearchDisplayQuery, normalizeSearchMatchQuery } from '@core/search/searchQuery.ts';
import { normalizeRemoteResults } from '@core/search/searchResultNormalization.ts';
import type { SearchResultsResponse } from '@core/api/contracts/searchContracts.ts';
import type { SearchItem, SearchOptions } from '@core/search/searchTypes.ts';
import { collectSearchResults, mergeSearchResults } from '@features/search/panel/mappers.ts';
import type { SearchBackendState } from '@features/search/panel/state.ts';

interface SearchExecutionContext {
    dependencies: {
        apiClient: {
            whenReady: (options: { allowDiscovery: boolean }) => Promise<string>;
            search: (query: string, limit: number, options?: SearchOptions) => Promise<SearchResultsResponse>;
        };
    };
    state: SearchBackendState;
    onSearchResults: (query: string, results: SearchItem[]) => void;
    ensureApiReady: () => Promise<void>;
    primeDataResources: () => Promise<void>;
    waitForSystemReady: (timeout: number) => Promise<boolean>;
}

const getSearchLocalResults = (context: SearchExecutionContext, term: string): SearchItem[] => {
    return collectSearchResults(context.state.ensureSearchIndex(), term);
};

const combineSearchResults = (remoteResults: SearchItem[], localResults: SearchItem[], limit: number, options: SearchOptions = {}): SearchItem[] => {
    return mergeSearchResults(remoteResults, localResults, options.presentation === 'page' ? null : limit);
};

const resolveSearchLimitAndOptions = (limitOrOptions: number | SearchOptions, options: SearchOptions): { limit: number; options: SearchOptions } => {
    if (typeof limitOrOptions === 'number') {
        return {
            limit: limitOrOptions,
            options
        };
    }
    return {
        limit: limitOrOptions.limit ?? 10,
        options: limitOrOptions
    };
};

const fetchRemoteResults = async (context: SearchExecutionContext, query: string, limit: number, options: SearchOptions): Promise<SearchItem[]> => {
    throwIfAborted(options.signal);
    const response = await handleApiResult(context.dependencies.apiClient.search(query, limit, options), {
        boundaryName: 'SearchPanel',
        silent: true,
        notifyOnError: false,
        rethrow: (error) => isAbortError(error),
        logErrors: false
    });
    throwIfAborted(options.signal);
    return normalizeRemoteResults(response);
};

const isSearchGenerationCurrent = (context: SearchExecutionContext, generation: number): boolean => context.state.isSearchGenerationActive(generation);

const executeRemoteSearch = async (context: SearchExecutionContext, query: string, limit: number, options: SearchOptions, cacheKey: string, baseResults: SearchItem[], generation: number, readyBeforeSearch = false): Promise<SearchItem[]> => {
    if (!isSearchGenerationCurrent(context, generation)) {
        return [];
    }
    const remoteResults = await fetchRemoteResults(context, query, limit, options);
    if (!isSearchGenerationCurrent(context, generation)) {
        return [];
    }
    const combined = combineSearchResults(remoteResults, baseResults, limit, options);
    if (combined.length > 0 || readyBeforeSearch || context.state.isSystemReady()) {
        context.state.searchCache.set(cacheKey, {
            results: combined,
            timestamp: Date.now(),
            partial: remoteResults.length === 0 && !readyBeforeSearch
        });
    } else {
        context.state.searchCache.delete(cacheKey);
    }
    return combined;
};

const scheduleRemoteSearch = (context: SearchExecutionContext, query: string, limit: number, options: SearchOptions, cacheKey: string, baseResults: SearchItem[], generation: number): void => {
    if (context.state.pendingRemoteSearches.has(cacheKey)) {
        return;
    }
    const task = Promise.resolve().then(async (): Promise<void> => {
        try {
            throwIfAborted(options.signal);
            await context.ensureApiReady();
            throwIfAborted(options.signal);
            await context.primeDataResources();
            throwIfAborted(options.signal);
            const ready = await context.waitForSystemReady(4000);
            throwIfAborted(options.signal);
            if (!isSearchGenerationCurrent(context, generation)) {
                return;
            }
            const results = await executeRemoteSearch(context, query, limit, options, cacheKey, baseResults, generation, ready);
            if (!isSearchGenerationCurrent(context, generation)) {
                return;
            }
            context.onSearchResults(query, results);
        } catch (error) {
            const runtimeError = ensureError(error);
            if (isAbortError(runtimeError)) {
                return;
            }
            errorHandler.debug('SearchPanel', 'Deferred API search failed', runtimeError);
        } finally {
            if (context.state.pendingRemoteSearches.get(cacheKey) === task) {
                context.state.pendingRemoteSearches.delete(cacheKey);
            }
        }
    });
    context.state.pendingRemoteSearches.set(cacheKey, task);
};

const searchCatalog = async (context: SearchExecutionContext, query: string, limitOrOptions: number | SearchOptions = 10, options: SearchOptions = {}): Promise<SearchItem[]> => {
    const searchTerm = normalizeSearchMatchQuery(query);
    if (!searchTerm || searchTerm.length < 2) {
        return [];
    }
    const remoteQuery = normalizeSearchDisplayQuery(query);

    const resolved = resolveSearchLimitAndOptions(limitOrOptions, options);
    const limit = resolved.limit;
    const resolvedOptions = resolved.options;
    const generation = context.state.getSearchGeneration();
    throwIfAborted(resolvedOptions.signal);
    const immediate = !!resolvedOptions.immediate;
    const cacheKey = `${createSearchCacheKey(searchTerm, limit)}::${resolvedOptions.presentation ?? 'compact'}`;
    const cached = context.state.searchCache.get(cacheKey);

    if (cached && Date.now() - cached.timestamp < context.state.cacheTimeout) {
        if (immediate && cached.partial) {
            scheduleRemoteSearch(context, remoteQuery, limit, resolvedOptions, cacheKey, cached.results, generation);
        }
        if (!immediate && cached.partial) {
            return [];
        }
        return cached.results;
    }

    const localResults = getSearchLocalResults(context, searchTerm);
    if (immediate && localResults.length > 0) {
        const combined = combineSearchResults([], localResults, limit, resolvedOptions);
        context.state.searchCache.set(cacheKey, {
            results: combined,
            timestamp: Date.now(),
            partial: true
        });
        scheduleRemoteSearch(context, remoteQuery, limit, resolvedOptions, cacheKey, combined, generation);
        return combined;
    }

    throwIfAborted(resolvedOptions.signal);
    await context.ensureApiReady();
    throwIfAborted(resolvedOptions.signal);
    await context.primeDataResources();
    throwIfAborted(resolvedOptions.signal);
    const readyBeforeSearch = await context.waitForSystemReady(4000);
    throwIfAborted(resolvedOptions.signal);
    return await executeRemoteSearch(context, remoteQuery, limit, resolvedOptions, cacheKey, immediate ? [] : localResults, generation, readyBeforeSearch);
};

export { searchCatalog, getSearchLocalResults, combineSearchResults };
