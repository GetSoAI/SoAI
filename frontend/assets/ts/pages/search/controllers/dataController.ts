/* SoAI - Search page data controller [frontend/assets/ts/pages/search/controllers/dataController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SearchItem, SearchOptions } from '@core/search/searchTypes.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { SearchComponentContract } from '@pages/search/contracts/contracts.ts';

const SEARCH_PAGE_FILE_RESULT_LIMIT = 200;

interface SearchDataControllerDependencies {
    searchComponent: SearchComponentContract;
}

interface SearchExecutionResult {
    items: SearchItem[];
    searchReady: boolean;
}

class SearchDataController {
    readonly #searchComponent: SearchComponentContract;

    constructor({ searchComponent }: SearchDataControllerDependencies) {
        this.#searchComponent = searchComponent;
    }

    async executeSearch(query: string, options: SearchOptions = {}): Promise<SearchExecutionResult> {
        const items = await this.#searchComponent.search(query, 20, { ...options, presentation: 'page' });
        const searchReady = isFunction(this.#searchComponent.isSystemReady) ? this.#searchComponent.isSystemReady() : true;

        return {
            items,
            searchReady
        };
    }

    async executeFileSearch(query: string, options: SearchOptions = {}): Promise<SearchItem[]> {
        return await this.#searchComponent.searchFiles(query, SEARCH_PAGE_FILE_RESULT_LIMIT, options);
    }
}

export { SearchDataController };
