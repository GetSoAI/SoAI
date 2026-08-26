/* SoAI - Chat attach modal tab state [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachModalTabsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { TabsComponent } from '@core/ui/controls/Tabs.ts';
import type { TabConfig } from '@core/ui/controls/tabs/types.ts';
import { CHAT_ATTACH_MODAL_ID } from '@features/chat/public.ts';
import type { ChatAttachAvailabilityHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';
import { requireChatAttachModalChild } from '@pages/chat/controllers/modals/chatattach/chatAttachModalElementsManager.ts';

type ChatAttachModalTab = 'upload' | 'camera' | 'browse' | 'soaiLink' | 'knowledge';

interface ChatAttachModalOpenOptions {
    initialTab?: ChatAttachModalTab;
}

const CHAT_ATTACH_MODAL_TABS: readonly ChatAttachModalTab[] = Object.freeze(['upload', 'camera', 'browse', 'soaiLink', 'knowledge']);

const isChatAttachModalTab = (value: string | null): value is ChatAttachModalTab => value === 'upload' || value === 'camera' || value === 'browse' || value === 'soaiLink' || value === 'knowledge';

const chatAttachModalTabToken = (tab: ChatAttachModalTab): string => {
    if (tab === 'soaiLink') {
        return 'soai-link';
    }
    return tab;
};

const chatAttachTabComponentId = (tab: ChatAttachModalTab): string => modalUiId(CHAT_ATTACH_MODAL_ID, `tab-${chatAttachModalTabToken(tab)}`);

const requireChatAttachTabButton = (modal: HTMLElement, tab: ChatAttachModalTab): HTMLButtonElement => {
    const tabButton = dom.resolve(`[data-tab="${chatAttachTabComponentId(tab)}"]`, modal);
    if (!(tabButton instanceof HTMLButtonElement)) {
        throw new Error(`Chat attach modal requires "${tab}" tab button`);
    }
    return tabButton;
};

const resolveChatAttachTabFromComponentId = (tabId: string): ChatAttachModalTab | null => {
    for (const tab of CHAT_ATTACH_MODAL_TABS) {
        if (tabId === chatAttachTabComponentId(tab)) {
            return tab;
        }
    }
    return null;
};

const createChatAttachTabConfigs = (): TabConfig[] => [
    { id: chatAttachTabComponentId('upload'), label: i18n.t('chat.attachModal.tabUpload') },
    { id: chatAttachTabComponentId('camera'), label: i18n.t('chat.attachModal.tabCamera') },
    { id: chatAttachTabComponentId('browse'), label: i18n.t('chat.attachModal.tabBrowse') },
    { id: chatAttachTabComponentId('soaiLink'), label: i18n.t('chat.attachModal.tabSoaiLink') },
    { id: chatAttachTabComponentId('knowledge'), label: i18n.t('chat.attachModal.tabKnowledge') }
];

const createChatAttachTabsComponent = async (modal: HTMLElement, activeTab: ChatAttachModalTab, onTabSelected: (tab: ChatAttachModalTab) => void): Promise<TabsComponent> => {
    const tabsContainer = requireChatAttachModalChild(modal, 'tabs');
    const tabsComponent = new TabsComponent(tabsContainer, {
        tabs: createChatAttachTabConfigs(),
        activeTab: chatAttachTabComponentId(activeTab),
        className: 'tabs',
        enableOverflowNav: false,
        onTabChange: (activeTab: string): void => {
            const tab = resolveChatAttachTabFromComponentId(activeTab);
            if (tab !== null) {
                onTabSelected(tab);
            }
        }
    });
    await tabsComponent.initialize();
    return tabsComponent;
};

const isChatAttachTabAvailable = (host: ChatAttachAvailabilityHost, tab: ChatAttachModalTab): boolean => {
    if (tab === 'upload') {
        return host.attachments.fileUploadEnabled();
    }
    if (tab === 'camera') {
        return host.attachments.cameraEnabled();
    }
    return true;
};

const requireChatAttachTabAvailable = (host: ChatAttachAvailabilityHost, tab: ChatAttachModalTab): void => {
    if (!isChatAttachTabAvailable(host, tab)) {
        throw new Error(`Chat attach tab is not available: ${tab}`);
    }
};

const resolveFirstAvailableChatAttachTab = (host: ChatAttachAvailabilityHost): ChatAttachModalTab => {
    const tab = CHAT_ATTACH_MODAL_TABS.find((candidate) => isChatAttachTabAvailable(host, candidate));
    if (!tab) {
        throw new Error('Chat attach modal requires at least one available tab');
    }
    return tab;
};

const syncChatAttachTabAvailability = (host: ChatAttachAvailabilityHost, tabsComponent: TabsComponent): void => {
    const activeTab = resolveChatAttachTabFromComponentId(tabsComponent.getActiveTab() ?? '');
    if (activeTab !== null && !isChatAttachTabAvailable(host, activeTab)) {
        tabsComponent.setActiveTab(chatAttachTabComponentId(resolveFirstAvailableChatAttachTab(host)));
    }
    for (const tab of CHAT_ATTACH_MODAL_TABS) {
        if (isChatAttachTabAvailable(host, tab)) {
            tabsComponent.enableTab(chatAttachTabComponentId(tab));
        } else {
            tabsComponent.disableTab(chatAttachTabComponentId(tab));
        }
    }
};

const setChatAttachTabState = (modal: HTMLElement, tab: ChatAttachModalTab, activeTab: ChatAttachModalTab): void => {
    const isActive = tab === activeTab;
    const tabButton = requireChatAttachTabButton(modal, tab);
    const pane = requireChatAttachModalChild(modal, `pane-${chatAttachModalTabToken(tab)}`);
    tabButton.classList.toggle('is-active', isActive);
    tabButton.setAttribute('aria-selected', isActive ? 'true' : 'false');
    tabButton.setAttribute('tabindex', isActive ? '0' : '-1');
    pane.classList.toggle('is-active', isActive);
    pane.toggleAttribute('hidden', !isActive);
    pane.setAttribute('aria-hidden', isActive ? 'false' : 'true');
};

const activateChatAttachTab = (modal: HTMLElement, tab: ChatAttachModalTab): void => {
    for (const candidate of CHAT_ATTACH_MODAL_TABS) {
        setChatAttachTabState(modal, candidate, tab);
    }
};

const resolveInitialChatAttachTab = (modal: HTMLElement, options: ChatAttachModalOpenOptions): ChatAttachModalTab => {
    if (options.initialTab) {
        return options.initialTab;
    }
    const lastUsedTab = modal.dataset['chatAttachActiveTab'] ?? null;
    if (isChatAttachModalTab(lastUsedTab)) {
        return lastUsedTab;
    }
    return 'upload';
};

export { activateChatAttachTab, createChatAttachTabsComponent, requireChatAttachTabAvailable, resolveInitialChatAttachTab, syncChatAttachTabAvailability };
export type { ChatAttachModalOpenOptions, ChatAttachModalTab };
