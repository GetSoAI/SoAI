/* SoAI - Search feature panel contracts [frontend/assets/ts/features/search/panel/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SearchResultsResponse } from '@core/api/contracts/searchContracts.ts';
import type { ConnectionEvent, StatusSnapshot } from '@core/connectionstatus/public.ts';
import type { GetStreamManagerOptions, PeekStreamManagerOptions } from '@core/lifecyclemodel/types.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import type { SearchIndexContributor, SearchStaticIndexContributor } from '@core/search/protocols.ts';
import type { SearchIndex, SearchItem, SearchOptions } from '@core/search/searchTypes.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { DisposableResource } from '@core/resourcetracker/types.ts';
import type { FileSearchApiClient } from '@features/search/panel/fileResults.ts';

type SearchIndexKey = keyof SearchIndex;

interface SearchBackendDependencies {
    apiClient: {
        whenReady: (options: { allowDiscovery: boolean }) => Promise<string>;
        search: (query: string, limit: number, options?: SearchOptions) => Promise<SearchResultsResponse>;
    } & FileSearchApiClient;
    storage: {
        getRecentSearches?: () => string[];
        clearRecentSearches?: () => void;
    };
    connectionStatus: {
        subscribe: (callback: (error: ConnectionEvent) => void, options: { emitCurrent?: boolean }) => (() => void) | null;
        getInitialSnapshot: (options: { timeout?: number }) => Promise<StatusSnapshot | null>;
        getSnapshot?: () => StatusSnapshot | null;
    };
    getStreamManager: (options: GetStreamManagerOptions) => Promise<StreamRuntimeOwners>;
    peekStreamManager: (options: PeekStreamManagerOptions) => StreamRuntimeOwners | null;
    searchContributors: readonly SearchIndexContributor[];
    staticContributors: readonly SearchStaticIndexContributor[];
    trackResource: <T extends DisposableResource>(resource: T) => void;
    onIndexUpdated: (type: string, size: number | null) => void;
    onMeta: (type: string, data: JsonValue) => void;
    onSearchResults: (query: string, results: SearchItem[]) => void;
}

export type { SearchIndexKey, SearchBackendDependencies };
