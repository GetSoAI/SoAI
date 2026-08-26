/* SoAI - Frontend search panel execution context [frontend/assets/ts/features/search/panel/executionContext.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SearchItem } from '@core/search/searchTypes.ts';
import type { SearchBackendDependencies } from '@features/search/panel/contracts.ts';
import type { SearchBackendState } from '@features/search/panel/state.ts';

interface SearchExecutionContext {
    dependencies: {
        apiClient: SearchBackendDependencies['apiClient'];
    };
    onSearchResults: (query: string, results: SearchItem[]) => void;
    ensureApiReady: () => Promise<void>;
    primeDataResources: () => Promise<void>;
    waitForSystemReady: (timeout: number) => Promise<boolean>;
    state: SearchBackendState;
}

interface SearchExecutionBackend {
    readonly apiClient: SearchBackendDependencies['apiClient'];
    readonly state: SearchBackendState;
    searchResultsDispatched(query: string, results: SearchItem[]): void;
    ensureApiReady(): Promise<void>;
    primeDataResources(): Promise<void>;
    waitForSystemReady(timeout: number): Promise<boolean>;
}

const createSearchExecutionContext = (backend: SearchExecutionBackend): SearchExecutionContext => ({
    dependencies: {
        apiClient: backend.apiClient
    },
    onSearchResults: (query: string, results: SearchItem[]) => backend.searchResultsDispatched(query, results),
    ensureApiReady: () => backend.ensureApiReady(),
    primeDataResources: () => backend.primeDataResources(),
    waitForSystemReady: (timeout: number) => backend.waitForSystemReady(timeout),
    state: backend.state
});

export { createSearchExecutionContext };
export type { SearchExecutionContext };
