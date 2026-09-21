/* SoAI - Chat page search UI [frontend/assets/ts/pages/chat/widgets/chatSearchUi.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { SearchBar } from '@features/controls/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface ChatSearchUiHost extends PageDomOwnerHost {
    getSearchQuery(): string;
    setSearchQuery(query: string): void;
    onSearchChanged(): Promise<void>;
    resetSearchBar(): void;
    setCurrentSearchBar(searchBar: SearchBar): void;
    getCurrentSearchBar(): SearchBar | null;
}

const initializeChatSearchUi = (host: ChatSearchUiHost): void => {
    const container = host.pageDom.optionalHTMLElement('.chat-search-container');
    if (!container) {
        host.resetSearchBar();
        return;
    }

    const applyQuery = (query: string): Promise<void> => {
        host.setSearchQuery(query);
        return host.onSearchChanged();
    };

    const existingSearchBar = host.getCurrentSearchBar();
    const existingSearchBarContainer = existingSearchBar?.getContainer() ?? null;
    const hasLiveSearchBar = existingSearchBar instanceof SearchBar && existingSearchBarContainer instanceof HTMLElement && container.contains(existingSearchBarContainer);

    if (!hasLiveSearchBar) {
        host.resetSearchBar();
        const existingSearchbarContainer = host.pageDom.optionalHTMLElement('.searchbar-container', container);
        if (existingSearchbarContainer) {
            existingSearchbarContainer.remove();
        }

        const searchBar = new SearchBar({
            id: 'chat-search-input',
            placeholder: i18n.t('chat.search.placeholder'),
            width: 'auto',
            containerClass: 'chat-search',
            debounceTime: 300,
            onSearch: async (query: string): Promise<void> => {
                await applyQuery(query);
            },
            onClear: async (): Promise<void> => {
                await applyQuery('');
            }
        });
        host.setCurrentSearchBar(searchBar);

        searchBar.initialize(container);
    } else {
        existingSearchBar.updateOptions({ placeholder: i18n.t('chat.search.placeholder') });
    }

    const searchQuery = host.getSearchQuery();
    const activeSearchBar = host.getCurrentSearchBar();
    if (activeSearchBar && searchQuery !== activeSearchBar.getValue()) {
        activeSearchBar.setValue(searchQuery, false);
    }
};

export { initializeChatSearchUi };
export type { ChatSearchUiHost };
