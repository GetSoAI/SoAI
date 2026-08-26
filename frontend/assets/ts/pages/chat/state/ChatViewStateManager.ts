/* SoAI - Chat presentation and render state ownership [frontend/assets/ts/pages/chat/state/ChatViewStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SearchBar } from '@features/controls/public.ts';
import { IconMarkupCache } from '@core/ui/icons/iconMarkupCache.ts';
import { normalizeSearchMatchQuery } from '@core/search/searchQuery.ts';
import type { ChatSearchUiHost } from '@pages/chat/widgets/chatSearchUi.ts';

interface ConversationRenderCache {
    conversationKey: string;
    viewState: 'messages' | 'empty' | 'loading' | 'error';
    domIdsInOrder: string[];
    renderSignatureByDomId: Map<string, string>;
}

class ChatViewState {
    #searchQuery = '';
    #searchQueryLower = '';
    sidebarOpen = true;
    showFavoritesAtTop = false;
    readonly iconCache = new IconMarkupCache({ maxEntries: 100 });
    readonly conversationListMetricsCache = new Map<string, { updatedAt: number; isChatStreaming: boolean; logicalCount: number }>();
    conversationRenderCache: ConversationRenderCache | null = null;
    searchBar: SearchBar | null = null;
    activeColorPickerConversationId: string | null = null;
    activeColorPickerElement: HTMLElement | null = null;
    searchUiHost: ChatSearchUiHost | null = null;

    get searchQuery(): string {
        return this.#searchQuery;
    }

    get searchQueryLower(): string {
        return this.#searchQueryLower;
    }

    setSearchQuery(query: string): void {
        this.#searchQuery = query;
        this.#searchQueryLower = normalizeSearchMatchQuery(query);
    }
}

export { ChatViewState };
export type { ConversationRenderCache };
export interface ChatViewStateHost {
    viewState: ChatViewState;
}
