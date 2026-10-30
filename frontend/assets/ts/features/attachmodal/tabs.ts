/* SoAI - Chat attach modal tab state [frontend/assets/ts/features/attachmodal/tabs.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ATTACH_MODAL_ID } from '@features/attachmodal/constants.ts';
import { ATTACH_MODAL_TABS, type AttachModalConsumer, type AttachModalOpenOptions, type AttachModalTab } from '@features/attachmodal/contracts.ts';

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { TabsComponent } from '@core/ui/controls/Tabs.ts';
import { updateTabSelectionState } from '@core/ui/controls/tabs/effects.ts';
import { requireAttachModalChild } from '@features/attachmodal/elements.ts';

const isAttachModalTab = (value: string | null): value is AttachModalTab => value === 'upload' || value === 'camera' || value === 'browse' || value === 'soaiLink' || value === 'knowledge';

const attachModalTabToken = (tab: AttachModalTab): string => {
    if (tab === 'soaiLink') {
        return 'soai-link';
    }
    return tab;
};

const attachTabComponentId = (tab: AttachModalTab): string => modalUiId(ATTACH_MODAL_ID, `tab-${attachModalTabToken(tab)}`);

const requireAttachTabButton = (modal: HTMLElement, tab: AttachModalTab): HTMLButtonElement => {
    const tabButton = dom.resolve(`[data-tab="${attachTabComponentId(tab)}"]`, modal);
    if (!(tabButton instanceof HTMLButtonElement)) {
        throw new Error(`Chat attach modal requires "${tab}" tab button`);
    }
    return tabButton;
};

const resolveAttachTabFromComponentId = (tabId: string): AttachModalTab | null => {
    for (const tab of ATTACH_MODAL_TABS) {
        if (tabId === attachTabComponentId(tab)) {
            return tab;
        }
    }
    return null;
};

const resolveAttachTabLabel = (tab: AttachModalTab): string => {
    switch (tab) {
        case 'upload':
            return i18n.t('chat.attachModal.tabUpload');
        case 'camera':
            return i18n.t('chat.attachModal.tabCamera');
        case 'browse':
            return i18n.t('chat.attachModal.tabBrowse');
        case 'soaiLink':
            return i18n.t('chat.attachModal.tabSoaiLink');
        case 'knowledge':
            return i18n.t('chat.attachModal.tabKnowledge');
    }
};

const syncAttachTabBadges = (host: AttachModalConsumer, tabsComponent: TabsComponent): void => {
    const counts = host.counts();
    for (const tab of host.policy.enabledTabs) {
        const count = counts[tab];
        tabsComponent.updateTabBadge(attachTabComponentId(tab), count > 0 ? count : null);
    }
};

const createAttachTabsComponent = (modal: HTMLElement, activeTab: AttachModalTab, enabledTabs: readonly AttachModalTab[], onTabSelected: (tab: AttachModalTab) => void): TabsComponent => {
    const tabsContainer = requireAttachModalChild(modal, 'tabs');
    const tabsComponent = new TabsComponent(tabsContainer, {
        tabs: enabledTabs.map((tab) => ({ id: attachTabComponentId(tab), label: resolveAttachTabLabel(tab) })),
        activeTab: attachTabComponentId(activeTab),
        className: 'tabs',
        onTabChange: (activeTab: string): void => {
            const tab = resolveAttachTabFromComponentId(activeTab);
            if (tab !== null) {
                onTabSelected(tab);
            }
        }
    });
    return tabsComponent;
};

const isAttachTabAvailable = (host: AttachModalConsumer, tab: AttachModalTab): boolean => host.policy.enabledTabs.includes(tab) && host.isAvailable(tab);

const requireAttachTabAvailable = (host: AttachModalConsumer, tab: AttachModalTab): void => {
    if (!isAttachTabAvailable(host, tab)) {
        throw new Error(`Chat attach tab is not available: ${tab}`);
    }
};

const resolveFirstAvailableAttachTab = (host: AttachModalConsumer): AttachModalTab => {
    const tab = host.policy.enabledTabs.find((candidate) => isAttachTabAvailable(host, candidate));
    if (!tab) {
        throw new Error('Chat attach modal requires at least one available tab');
    }
    return tab;
};

const syncAttachTabAvailability = (host: AttachModalConsumer, tabsComponent: TabsComponent): void => {
    const activeTab = resolveAttachTabFromComponentId(tabsComponent.getActiveTab() ?? '');
    if (activeTab !== null && !isAttachTabAvailable(host, activeTab)) {
        tabsComponent.setActiveTab(attachTabComponentId(resolveFirstAvailableAttachTab(host)));
    }
    for (const tab of host.policy.enabledTabs) {
        if (isAttachTabAvailable(host, tab)) {
            tabsComponent.enableTab(attachTabComponentId(tab));
        } else {
            tabsComponent.disableTab(attachTabComponentId(tab), host.disabledLabel(tab));
        }
    }
};

const setAttachTabState = (modal: HTMLElement, tab: AttachModalTab, activeTab: AttachModalTab): void => {
    const isActive = tab === activeTab;
    const tabButton = requireAttachTabButton(modal, tab);
    const pane = requireAttachModalChild(modal, `pane-${attachModalTabToken(tab)}`);
    tabButton.classList.toggle('is-active', isActive);
    tabButton.setAttribute('tabindex', isActive ? '0' : '-1');
    updateTabSelectionState(tabButton, pane, isActive);
};

const activateAttachTab = (modal: HTMLElement, tab: AttachModalTab, enabledTabs: readonly AttachModalTab[]): void => {
    for (const candidate of enabledTabs) {
        setAttachTabState(modal, candidate, tab);
    }
};

const resolveInitialAttachTab = (host: AttachModalConsumer, modal: HTMLElement, options: AttachModalOpenOptions, currentTab?: AttachModalTab): AttachModalTab => {
    if (options.initialTab && isAttachTabAvailable(host, options.initialTab)) {
        return options.initialTab;
    }
    if (currentTab !== undefined && isAttachTabAvailable(host, currentTab)) return currentTab;
    const lastUsedTab = modal.dataset['chatAttachActiveTab'] ?? null;
    if (isAttachModalTab(lastUsedTab) && isAttachTabAvailable(host, lastUsedTab)) {
        return lastUsedTab;
    }
    return isAttachTabAvailable(host, 'upload') ? 'upload' : resolveFirstAvailableAttachTab(host);
};

export { activateAttachTab, attachTabComponentId, createAttachTabsComponent, requireAttachTabAvailable, resolveInitialAttachTab, syncAttachTabAvailability, syncAttachTabBadges };
export type { AttachModalOpenOptions, AttachModalTab };
