/* SoAI - Chat page icons [frontend/assets/ts/pages/chat/controllers/page/dom/icons.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconDefinition } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { CHAT_SELECTORS } from '@features/chat/public.ts';
import { CHAT_BASE_ICON_MAP, CHAT_INPUT_ACTION_ICON_MAP } from '@pages/chat/contracts/chatPageConfig.ts';
import type { ChatIconResolver, ChatPageDomHost } from '@pages/chat/controllers/page/dom/contracts.ts';

const requireNewConversationControls = (host: ChatPageDomHost): void => {
    if (host.services.isDetached()) {
        return;
    }
    const hasSidebarButton = host.pageDom.optionalHTMLElement('.new-conversation-btn');
    const hasHeaderButton = host.pageDom.optionalHTMLElement('.new-conversation-header-btn');
    if (!hasSidebarButton && !hasHeaderButton) {
        throw new Error('Chat required UI missing: no elements found for selectors ".new-conversation-btn" or ".new-conversation-header-btn"');
    }
};

const resolveChatBaseIconMap = (host: ChatPageDomHost): Record<string, IconDefinition> => {
    requireNewConversationControls(host);
    return { ...CHAT_BASE_ICON_MAP };
};

const applyIconMap = (
    host: ChatPageDomHost,
    iconMap: Record<string, IconDefinition>,
    options: {
        resolver: (name: IconName, options?: IconOptions) => TrustedHtml;
    }
): void => {
    const filteredMap: Record<string, IconDefinition> = {};
    for (const [selector, definition] of Object.entries(iconMap)) {
        if (host.pageDom.optionalHTMLElement(selector) !== null) {
            filteredMap[selector] = definition;
        }
    }
    host.services.applyIconMap(filteredMap, options.resolver);
};

const insertIcons = (host: ChatPageDomHost, sidebarOpen: boolean, showFavoritesAtTop: boolean, getIcon: ChatIconResolver): void => {
    const baseIcons = resolveChatBaseIconMap(host);
    applyIconMap(host, baseIcons, {
        resolver: (name: IconName, options?: IconOptions) => getIcon(name, options)
    });
    applyIconMap(host, CHAT_INPUT_ACTION_ICON_MAP, {
        resolver: (name: IconName, options?: IconOptions) => getIcon(name, options)
    });

    if (!host.services.isDetached()) {
        host.pageDom.updateHtml(CHAT_SELECTORS.SIDEBAR_TOGGLE, getIcon(sidebarOpen ? 'panel-left-visible' : 'panel-hidden', { size: 16, strokeWidth: 1.5 }), { escape: false });
    }

    const favoriteButton = host.pageDom.optionalHTMLElement('.favorite-toggle-btn');
    if (favoriteButton) {
        host.pageDom.toggleClass(favoriteButton, 'is-active', showFavoritesAtTop);
    }
};

export { insertIcons };
