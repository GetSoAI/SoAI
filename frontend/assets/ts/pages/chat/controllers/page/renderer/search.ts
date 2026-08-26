/* SoAI - Chat page search [frontend/assets/ts/pages/chat/controllers/page/renderer/search.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatSearchDependencies } from '@pages/chat/controllers/page/renderer/contracts.ts';
import { initializeChatSearchUi } from '@pages/chat/widgets/chatSearchUi.ts';

const initializeChatSearch = (host: ChatSearchDependencies): void => {
    if (!host.viewState.searchUiHost) {
        host.viewState.searchUiHost = {
            pageDom: host.pageDom,
            getSearchQuery: (): string => host.viewState.searchQuery,
            setSearchQuery: (query: string): void => {
                host.viewState.setSearchQuery(query);
            },
            onSearchChanged: async (): Promise<void> => {
                await host.renderConversationList();
            },
            resetSearchBar: (): void => {
                host.viewState.searchBar?.dispose();
                host.viewState.searchBar = null;
            },
            setCurrentSearchBar: (searchBar) => {
                host.viewState.searchBar = searchBar;
            },
            getCurrentSearchBar: () => host.viewState.searchBar,
            getSearchIconMarkup: () => {
                return host.services.getIconSync('search', { size: 16, strokeWidth: 1.5 });
            }
        };
    }
    initializeChatSearchUi(host.viewState.searchUiHost);
};

export { initializeChatSearch };
