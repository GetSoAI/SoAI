/* SoAI - Chat initial modal query handling [frontend/assets/ts/pages/chat/controllers/initialModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildRouteWithoutQueryParameters } from '@core/routing/router/events.ts';

interface ChatInitialModalHost {
    router: {
        getRouteParameters(): Record<string, string>;
        replaceCurrentRoute(target: string): void;
    } | null;
    configurationSession: { openTab(tabId: string): void };
}

const clearChatInitialModalQuery = (host: ChatInitialModalHost): void => {
    const router = host.router;
    if (!router) {
        throw new Error('Chat initial modal cleanup requires a router');
    }
    router.replaceCurrentRoute(buildRouteWithoutQueryParameters('chat', router.getRouteParameters(), ['modal']));
};

const handleChatInitialModal = (host: ChatInitialModalHost): void => {
    const router = host.router;
    if (!router) {
        throw new Error('Chat initial modal requires a router');
    }
    if (router.getRouteParameters()['modal'] !== 'chat-settings') {
        return;
    }
    host.configurationSession.openTab('general');
    clearChatInitialModalQuery(host);
};

export { handleChatInitialModal };
