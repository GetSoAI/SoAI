/* SoAI - Chat page configuration tabs host controller [frontend/assets/ts/pages/chat/controllers/chatConfigurationTabsHostController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { ChatConversationSettingsManager } from '@features/chat/public.ts';
import type { ChatConfigurationTabsHost } from '@pages/chat/widgets/chatconfigurationtabs/ChatConfigurationTabsController.ts';
import type { ChatConfigurationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { PageLayoutOwnerHost } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface ChatConfigurationTabsPageHost extends ChatConfigurationRuntimeOwner, PageLayoutOwnerHost, PageDomOwnerHost {
    getConversationSettingsManager(): ChatConversationSettingsManager | null;
}

interface ChatConfigurationTabsHostOptions {
    page: ChatConfigurationTabsPageHost;
    refreshMemoryTabInBackground(contextMessage: string): void;
    onTabChange?(tabId: string): void;
}

const createChatConfigurationTabsHost = (options: ChatConfigurationTabsHostOptions): ChatConfigurationTabsHost => {
    const page = options.page;
    return {
        pageDom: page.pageDom,
        getActiveTab: (): string => page.configurationRuntime.requireConfiguration().getActiveTab(),
        setActiveTab: (tabId: string): void => page.configurationRuntime.requireConfiguration().setActiveTab(tabId),
        initializeTabs: (container, tabsOptions) => page.layout.initializeTabs(container, tabsOptions),
        getTabsComponent: () => page.layout.getTabs(),
        queryModalTabContents: (modal: HTMLElement): Element[] => dom.resolveAll('.tab-content', modal),
        setTabContentActive: (element: Element, active: boolean): void => {
            element.classList.toggle('is-active', active);
        },
        resetConfigurationScroll: (modal: HTMLElement): void => {
            const body = dom.resolve('.chat-configuration-scroll', modal);
            if (body instanceof HTMLElement) {
                body.scrollTop = 0;
                body.scrollLeft = 0;
            }
        },
        onConversationSettingsTabChange: (tabId: string): void => {
            options.onTabChange?.(tabId);
            if (tabId === 'memory') {
                options.refreshMemoryTabInBackground('Unexpected refreshMemoryTab rejection while switching to memory tab');
            }
            page.getConversationSettingsManager()?.handleConfigurationTabChange?.(tabId);
        }
    };
};

export { createChatConfigurationTabsHost };
export type { ChatConfigurationTabsHostOptions, ChatConfigurationTabsPageHost };
