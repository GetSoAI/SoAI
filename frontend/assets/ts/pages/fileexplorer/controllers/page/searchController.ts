/* SoAI - File explorer page control layer search controller [frontend/assets/ts/pages/fileexplorer/controllers/page/searchController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { i18n } from '@core/i18n/index.ts';
import type { StandardSearchResult } from '@core/routing/pages/pagetypes/public.ts';
import { normalizeSearchDisplayQuery } from '@core/search/searchQuery.ts';
import { FILE_EXPLORER_SEARCH_CONTAINER_SELECTOR } from '@pages/fileexplorer/contracts/contracts.ts';

interface FileExplorerPageSearchControllerHost {
    requireHTMLElement: (selector: string) => HTMLElement;
    createStandardSearch: (container: HTMLElement, options: { placeholder: string; onSearch: (query: string) => void; onClear: () => void; showIconOnMobile?: boolean }) => StandardSearchResult;
    runUiTask: (operation: string, task: () => Promise<void> | void) => Promise<void>;
    search: (query: string) => Promise<void>;
    clearSearch: () => Promise<void>;
    isDisposed: () => boolean;
}

class FileExplorerPageSearchController {
    readonly #host: FileExplorerPageSearchControllerHost;
    readonly #searchResult: StandardSearchResult;
    #sequence = 0;

    constructor(host: FileExplorerPageSearchControllerHost) {
        this.#host = host;
        this.#searchResult = host.createStandardSearch(host.requireHTMLElement(FILE_EXPLORER_SEARCH_CONTAINER_SELECTOR), {
            placeholder: i18n.t('fileExplorer.searchPlaceholder'),
            onSearch: (query) => this.#handleSearch(query),
            onClear: () => this.#handleClear(),
            showIconOnMobile: true
        });
    }

    resetOnNavigation(): void {
        if (this.#host.isDisposed()) {
            return;
        }
        this.#sequence += 1;
        this.#searchResult.setValue('');
    }

    async applyInitialSearch(query: string): Promise<void> {
        if (this.#host.isDisposed()) {
            return;
        }
        this.#sequence += 1;
        this.#searchResult.setValue(query);
        await this.#host.search(query);
    }

    #handleSearch(query: string): void {
        const normalizedQuery = normalizeSearchDisplayQuery(query);
        if (this.#host.isDisposed() || !normalizedQuery || normalizeSearchDisplayQuery(this.#searchResult.input.value) !== normalizedQuery) {
            return;
        }
        const sequence = this.#sequence;
        terminateHandledPromise(
            this.#host.runUiTask('fileExplorer:search:query', async () => {
                if (this.#host.isDisposed() || sequence !== this.#sequence) {
                    return;
                }
                await this.#host.search(query);
            })
        );
    }

    #handleClear(): void {
        if (this.#host.isDisposed()) {
            return;
        }
        this.#sequence += 1;
        terminateHandledPromise(
            this.#host.runUiTask('fileExplorer:search:clear', async () => {
                if (this.#host.isDisposed()) {
                    return;
                }
                await this.#host.clearSearch();
            })
        );
    }
}

export { FileExplorerPageSearchController };
export type { FileExplorerPageSearchControllerHost };
