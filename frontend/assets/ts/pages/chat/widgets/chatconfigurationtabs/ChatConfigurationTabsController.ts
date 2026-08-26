/* SoAI - Chat configuration tabs ownership [frontend/assets/ts/pages/chat/widgets/chatconfigurationtabs/ChatConfigurationTabsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { runCleanup } from '@core/lifecycle/cleanup.ts';
import { isString } from '@core/typeGuards.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { CHAT_CONFIGURATION_MODAL_ID, CHAT_CONFIGURATION_TAB_DEFINITIONS, resolveChatConfigurationTabId, resolveChatConfigurationTabLabel } from '@features/chat/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface TabsComponentContract {
    activeTab: string | null;
    initialize: () => Promise<boolean>;
    dispose?: () => void;
}

interface ChatConfigurationTab {
    id: string;
    label: string;
}

interface ChatConfigurationTabsHost extends PageDomOwnerHost {
    getActiveTab(): string;
    setActiveTab(tabId: string): void;
    initializeTabs(
        container: HTMLElement,
        options: {
            tabs: ChatConfigurationTab[];
            activeTab: string;
            className: string;
            onTabChange: (next: string) => void;
        }
    ): TabsComponentContract | null;
    getTabsComponent(): TabsComponentContract | null;
    queryModalTabContents(modal: HTMLElement): Element[];
    setTabContentActive(element: Element, active: boolean): void;
    resetConfigurationScroll(modal: HTMLElement): void;
    onConversationSettingsTabChange(tabId: string): void;
}

const applyChatConfigurationTabChange = (host: ChatConfigurationTabsHost, modalRoot: HTMLElement, tabId: string): void => {
    const normalizedTabId = resolveChatConfigurationTabId(tabId);
    const selectedTabDefinition = CHAT_CONFIGURATION_TAB_DEFINITIONS.find((entry) => entry.id === normalizedTabId);
    if (!selectedTabDefinition) {
        throw new Error(`Chat configuration tab definition is missing for id: ${normalizedTabId}`);
    }
    host.setActiveTab(normalizedTabId);
    host.queryModalTabContents(modalRoot).forEach((element) => {
        host.setTabContentActive(element, element.id === selectedTabDefinition.contentId);
    });
    host.resetConfigurationScroll(modalRoot);
    host.onConversationSettingsTabChange(normalizedTabId);
};

const initializeChatConfigurationTabs = async (host: ChatConfigurationTabsHost, modalRoot: HTMLElement): Promise<void> => {
    const container = host.pageDom.requireHTMLElement(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'tabs'), modalRoot);
    const tabs: ChatConfigurationTab[] = CHAT_CONFIGURATION_TAB_DEFINITIONS.map((entry) => ({
        id: entry.id,
        label: resolveChatConfigurationTabLabel(entry.id)
    }));
    const activeTab = host.getActiveTab();
    const tabsComponent = host.initializeTabs(container, {
        tabs,
        activeTab,
        className: 'tabs',
        onTabChange: (next: string): void => {
            const tabId = isString(next) ? next : resolveChatConfigurationTabId(activeTab);
            applyChatConfigurationTabChange(host, modalRoot, tabId);
        }
    });
    if (tabsComponent) {
        await tabsComponent.initialize();
    }
    let selectedTab = activeTab;
    if (tabsComponent && isString(tabsComponent.activeTab) && tabsComponent.activeTab) {
        selectedTab = tabsComponent.activeTab;
    }
    applyChatConfigurationTabChange(host, modalRoot, selectedTab);
};

const disposeTabsComponent = (tabsComponent: TabsComponentContract): void => {
    if (!tabsComponent.dispose) {
        return;
    }
    tabsComponent.dispose();
};

const disposeChatConfigurationTabs = (host: ChatConfigurationTabsHost): void => {
    const tabsComponent = host.getTabsComponent();
    runCleanup(tabsComponent ? () => disposeTabsComponent(tabsComponent) : null, (runtimeError) => {
        errorHandler.warn('ChatConfigurationTabs', 'Tabs cleanup failed', runtimeError);
    });
};

export { disposeChatConfigurationTabs, initializeChatConfigurationTabs };
export type { ChatConfigurationTabsHost, TabsComponentContract };
