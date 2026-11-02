/* SoAI - Chat initial modal query handling [frontend/assets/ts/pages/chat/controllers/initialModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { consumeRouteQuery, INITIAL_MODAL_QUERY_KEYS } from '@core/routeregistry/reconstruction.ts';
import type { PageMountScope, PageRouting } from '@core/routing/router/types.ts';
import { isPresentationOwnerFocused } from '@core/presentationOwner.ts';

interface ChatInitialModalHost {
    owner: PageMountScope;
    router: Pick<PageRouting, 'getRouteParameters' | 'getCurrentRoute' | 'getQueryParameters' | 'replaceCurrentRoute'> | null;
    configurationSession: { openTab(tabId: string): void };
}

const clearChatInitialModalQuery = (host: ChatInitialModalHost): void => {
    const router = host.router;
    if (!router) {
        throw new Error('Chat initial modal cleanup requires a router');
    }
    consumeRouteQuery(router, INITIAL_MODAL_QUERY_KEYS);
};

const handleChatInitialModal = (host: ChatInitialModalHost): void => {
    const router = host.router;
    if (!router) {
        throw new Error('Chat initial modal requires a router');
    }
    if (router.getRouteParameters()['modal'] !== 'chat-settings') {
        return;
    }
    if (!isPresentationOwnerFocused(host.owner)) return;
    host.configurationSession.openTab('general');
    clearChatInitialModalQuery(host);
};

export { handleChatInitialModal };
