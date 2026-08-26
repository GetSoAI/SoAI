/* SoAI - Search feature panel [frontend/assets/ts/features/search/SearchPanel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import type { SearchResultsResponse } from '@core/api/contracts/searchContracts.ts';
import type { ConnectionEvent, StatusSnapshot } from '@core/connectionstatus/public.ts';
import { dispatchCustomEvent } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { LifecycleModel } from '@core/LifecycleModel.ts';
import type { GetStreamManagerOptions, PeekStreamManagerOptions } from '@core/lifecyclemodel/types.ts';
import { onNavigationComplete, type NavigationEventDetail } from '@core/navigationEvents.ts';
import { isSearchIndexContributorList, isSearchStaticIndexContributorList } from '@core/search/guards.ts';
import { SEARCH_PANEL_SERVICE_ID, type SearchIndexContributor, type SearchStaticIndexContributor } from '@core/search/protocols.ts';
import type { SearchItem, SearchOptions, TypeMetadata } from '@core/search/searchTypes.ts';
import { subscribeToSoaiOsCapabilitiesChanges } from '@core/soaiOsAccess.ts';
import { isArray, isFunction, isNumber } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { DisposableResource } from '@core/resourcetracker/types.ts';
import type { FileSearchApiClient } from '@features/search/panel/fileResults.ts';
import { SearchBackend } from '@features/search/panel/service.ts';
import { DEFAULT_TYPE_METADATA_MAP, getTypeMetadata } from '@features/search/searchTypeMetadata.ts';

interface SearchPanelDependencies {
    apiClient: {
        whenReady: (options: { allowDiscovery: boolean }) => Promise<string>;
        search: (query: string, limit: number, options?: SearchOptions) => Promise<SearchResultsResponse>;
    } & FileSearchApiClient;
    storage: {
        getRecentSearches?: () => string[];
        clearRecentSearches?: () => void;
    };
    router: {
        getCurrentRoute: () => string | null;
    };
    connectionStatus: {
        subscribe: (callback: (error: ConnectionEvent) => void, options: { emitCurrent?: boolean }) => (() => void) | null;
        getInitialSnapshot: (options: { timeout?: number }) => Promise<StatusSnapshot | null>;
        getSnapshot?: () => StatusSnapshot | null;
    };
    auth: {
        onLogin?: (callback: () => void) => (() => void) | null;
        onLogout?: (callback: () => void) => (() => void) | null;
    } | null;
    searchContributors: readonly SearchIndexContributor[];
    staticContributors: readonly SearchStaticIndexContributor[];
    openPromptPreview: (promptId: string) => Promise<boolean>;
}

class SearchComponent extends LifecycleModel {
    #dependencies: SearchPanelDependencies;
    #backend: SearchBackend;
    readonly #realtimeInitializationToken = new SequenceToken();
    typeDisplayMap: Record<string, TypeMetadata>;

    constructor(dependencies: SearchPanelDependencies) {
        super({ moduleId: SEARCH_PANEL_SERVICE_ID, name: 'SearchPanel', type: 'component' });
        if (!dependencies.apiClient || !isFunction(dependencies.apiClient.whenReady) || !isFunction(dependencies.apiClient.search) || !dependencies.apiClient.fileExplorer || !isFunction(dependencies.apiClient.fileExplorer.search) || !isFunction(dependencies.apiClient.fileExplorer.metadata)) {
            throw new Error('SearchPanel requires an apiClient with whenReady, search, fileExplorer.search, and fileExplorer.metadata');
        }
        if (!dependencies.router || !isFunction(dependencies.router.getCurrentRoute)) {
            throw new Error('SearchPanel requires a router with getCurrentRoute');
        }
        if (!dependencies.connectionStatus || !isFunction(dependencies.connectionStatus.subscribe) || !isFunction(dependencies.connectionStatus.getInitialSnapshot)) {
            throw new Error('SearchPanel requires a connectionStatus monitor');
        }
        if (!isSearchIndexContributorList(dependencies.searchContributors)) {
            throw new Error('SearchPanel requires valid search contributors');
        }
        if (!isSearchStaticIndexContributorList(dependencies.staticContributors)) {
            throw new Error('SearchPanel requires valid static search contributors');
        }

        this.#dependencies = dependencies;
        this.typeDisplayMap = { ...DEFAULT_TYPE_METADATA_MAP };

        this.#backend = new SearchBackend({
            apiClient: dependencies.apiClient,
            storage: dependencies.storage,
            connectionStatus: dependencies.connectionStatus,
            getStreamManager: (options: GetStreamManagerOptions) => this.lifecycleStream.get(options),
            peekStreamManager: (options: PeekStreamManagerOptions) => this.lifecycleStream.peek(options),
            searchContributors: dependencies.searchContributors,
            staticContributors: dependencies.staticContributors,
            trackResource: <T extends DisposableResource>(resource: T) => this.lifecycleResources.track(resource),
            onIndexUpdated: (type: string, size: number | null) => this.#dispatchIndexUpdated(type, size),
            onMeta: (type: string, data: JsonValue) => this.#dispatchSearchMetaEvent(type, data),
            onSearchResults: (query: string, results: SearchItem[]) => this.#dispatchSearchResultsEvent(query, results)
        });
    }

    getTypeMetadata(category: string): TypeMetadata {
        return getTypeMetadata(category, this.typeDisplayMap);
    }

    override getRequiredResources(): string[] {
        return [];
    }

    isSystemReady(): boolean {
        return this.#backend.isSystemReady();
    }

    async initialize(): Promise<void> {
        if (this.isInitialized) return;
        if (this.isDestroyed) this.resetLifecycleState();
        await this.initializeLifecycle();
    }

    override async onInitialize(): Promise<void> {
        this.#backend.ensureSearchIndex();
        this.#backend.indexPages();
        this.setupEventListeners();
        this.#backend.loadRecentSearches();
        this.startCacheCleanup();
        const generation = this.#realtimeInitializationToken.next();
        void this.#initializeSearchData(generation).catch((error) => {
            errorHandler.warn('SearchPanel', 'Search data initialization failed', ensureError(error));
        });
    }

    override async onDestroy(): Promise<void> {
        this.#realtimeInitializationToken.invalidate();
        this.#backend.reset();
    }

    async #initializeSearchData(generation: number): Promise<void> {
        const permissionsApplied = await this.#backend.refreshGrantedActions();
        if (!permissionsApplied || !this.#realtimeInitializationToken.isActive(generation) || this.isDestroyed) {
            return;
        }
        await this.#backend.refreshStaticIndexes();
        if (!this.#realtimeInitializationToken.isActive(generation) || this.isDestroyed) {
            return;
        }
        this.#backend.indexPages();
        await this.#backend.monitorSystemReadiness();
        if (!this.#realtimeInitializationToken.isActive(generation) || this.isDestroyed) {
            return;
        }
        this.#backend.refreshIndexFromResources();
        await this.#backend.subscribeToDataStreams();
    }

    async search(query: string, limit: number | SearchOptions = 10, options: SearchOptions = {}): Promise<SearchItem[]> {
        return await this.#backend.search(query, limit, options);
    }

    async searchFiles(query: string, limit: number = 10, options: SearchOptions = {}): Promise<SearchItem[]> {
        return await this.#backend.searchFiles(query, limit, options);
    }

    async openPromptPreview(promptId: string): Promise<boolean> {
        return await this.#dependencies.openPromptPreview(promptId);
    }

    startCacheCleanup(): void {
        this.lifecycleResources.setTimer(() => this.#backend.cleanupExpiredCache(), 60000, { repeat: true });
    }

    refreshIndexFromResources(): void {
        this.#backend.refreshIndexFromResources();
    }

    async refreshStaticIndexes(): Promise<void> {
        await this.#backend.refreshStaticIndexes();
    }

    reindexPages(): void {
        this.#backend.indexPages();
        this.#backend.clearCacheForType('pages');
        this.#dispatchIndexUpdated('pages', this.#backend.ensureSearchIndex().pages?.size ?? 0);
    }

    setupEventListeners(): void {
        this.subscribeToAuthEvents();
        this.subscribeToRouterEvents();
        this.subscribeToSoaiOsCapabilitiesEvents();
        this.lifecycleResources.addEventListener(window, 'soai:language:changed', () => {
            terminateHandledPromise(this.refreshStaticIndexes());
            this.reindexPages();
        });
        this.lifecycleResources.addEventListener(window, 'soai:search:request-refresh', () => this.refreshAccessControlledIndexes('none'));
    }

    subscribeToAuthEvents(): void {
        const auth = this.#dependencies.auth;
        if (!auth) {
            return;
        }
        if (isFunction(auth.onLogin)) {
            this.lifecycleResources.track(
                auth.onLogin(() => {
                    this.refreshAccessControlledIndexes('load-recent');
                })
            );
        }
        if (isFunction(auth.onLogout)) {
            this.lifecycleResources.track(
                auth.onLogout(() => {
                    this.refreshAccessControlledIndexes('clear-recent');
                })
            );
        }
    }

    refreshAccessControlledIndexes(recentMode: 'clear-recent' | 'load-recent' | 'none'): void {
        this.#backend.resetGrantedActions();
        if (recentMode === 'load-recent') {
            this.#backend.loadRecentSearches();
        } else if (recentMode === 'clear-recent') {
            this.#backend.clearRecentSearches();
        }
        void this.#refreshAccessControlledIndexes().catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.error('SearchPanel', 'Access-controlled search refresh failed', runtimeError);
        });
    }

    async #refreshAccessControlledIndexes(): Promise<void> {
        const applied = await this.#backend.refreshGrantedActions();
        if (!applied) {
            return;
        }
        await this.refreshStaticIndexes();
        this.#backend.refreshIndexFromResources();
        this.reindexPages();
    }

    subscribeToRouterEvents(): void {
        try {
            const handler = (detail: NavigationEventDetail | null): void => {
                if (!detail) return;
                const component = detail.component ?? detail.resolvedRoute?.component ?? null;
                if (!component) return;
                const path = detail.route ?? this.#dependencies.router.getCurrentRoute() ?? '';
                this.#dispatchSearchMetaEvent('route', { component, path });
            };
            const unsubscribe = onNavigationComplete(handler);
            if (unsubscribe) {
                this.lifecycleResources.track(unsubscribe);
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('SearchPanel', 'Router subscription failed', runtimeError);
            throw runtimeError;
        }
    }

    subscribeToSoaiOsCapabilitiesEvents(): void {
        try {
            const unsubscribe = subscribeToSoaiOsCapabilitiesChanges(
                () => {
                    this.refreshStaticIndexes().catch((error) => errorHandler.warn('SearchPanel', 'Static index refresh after capability change failed', ensureError(error)));
                    this.reindexPages();
                },
                { immediate: false }
            );
            this.lifecycleResources.track(unsubscribe);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('SearchPanel', 'Failed to subscribe to SoAI OS capability updates', runtimeError);
            throw runtimeError;
        }
    }

    dispatchSearchResultsEvent(query: string, results: SearchItem[]): void {
        this.#dispatchSearchResultsEvent(query, results);
    }

    #dispatchSearchResultsEvent(query: string, results: SearchItem[]): void {
        if (isArray(results)) {
            dispatchCustomEvent('soai:search:results', { query, results });
        }
    }

    dispatchIndexUpdated(type: string, size: number | null = null): void {
        this.#dispatchIndexUpdated(type, size);
    }

    #dispatchIndexUpdated(type: string, size: number | null = null): void {
        dispatchCustomEvent('soai:search:index-updated', isNumber(size) ? { type, size } : { type });
    }

    dispatchSearchMetaEvent(type: string, data: JsonValue): void {
        this.#dispatchSearchMetaEvent(type, data);
    }

    #dispatchSearchMetaEvent(type: string, data: JsonValue): void {
        dispatchCustomEvent('soai:search:meta', { type, data });
    }
}

export { SearchComponent };
export type { SearchItem, SearchPanelDependencies };
