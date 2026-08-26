/* SoAI - Shared UI tabs actions [frontend/assets/ts/core/ui/controls/tabs/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';
import { findFirstEnabledTab, resolveNotifyBadgeText } from '@core/ui/controls/tabs/service.ts';
import type { TabConfig } from '@core/ui/controls/tabs/types.ts';

type ResolveTabElement = (selector: string) => Element | null;
type ActivateTab = (tabId: string) => void;

interface TabDisabledUpdateOptions {
    tabId: string;
    isDisabled: boolean;
    activeTab: string | null;
    tabs: TabConfig[];
    resolveElement: ResolveTabElement;
    activateTab: ActivateTab;
}

interface TabBadgeUpdateOptions {
    tabId: string;
    badge: string | number | null | undefined;
    tabs: TabConfig[];
    resolveElement: ResolveTabElement;
}

interface TabNotifyBadgeUpdateOptions {
    tabId: string;
    count: number;
    tabs: TabConfig[];
    resolveElement: ResolveTabElement;
}

const findTabById = (tabs: TabConfig[], tabId: string): TabConfig | null => {
    const tab = tabs.find((entry) => entry.id === tabId);
    return tab ?? null;
};

const resolveActiveTabAfterRemoval = (tabs: TabConfig[], activeTab: string | null, removedTabId: string): string | null => (activeTab === removedTabId ? (tabs[0]?.id ?? null) : activeTab);

const setTabDisabled = (options: TabDisabledUpdateOptions): void => {
    const tabElement = options.resolveElement(`[data-tab="${options.tabId}"]`);
    if (!tabElement) {
        return;
    }

    dom.setProperty(tabElement, 'disabled', options.isDisabled);

    if (!options.isDisabled || options.activeTab !== options.tabId) {
        return;
    }

    const firstEnabledTab = findFirstEnabledTab(options.tabs, (candidateTabId) => options.resolveElement(`[data-tab="${candidateTabId}"]`));
    if (firstEnabledTab) {
        options.activateTab(firstEnabledTab.id);
    }
};

const setRightButtonVisibility = (resolveElement: ResolveTabElement, buttonId: string, isVisible: boolean): void => {
    const buttonElement = resolveElement(`#${buttonId}`);
    if (!buttonElement) {
        return;
    }
    dom.setStyle(buttonElement, 'display', isVisible ? 'inline-flex' : 'none');
};

const updateTabBadge = (options: TabBadgeUpdateOptions): void => {
    const tab = findTabById(options.tabs, options.tabId);
    if (!tab) {
        return;
    }

    const badgeValue = options.badge;
    const hasBadge = !isNullOrUndefined(badgeValue) && badgeValue !== '';
    const existingBadge = options.resolveElement(`#${options.tabId}-badge`);

    if (hasBadge) {
        const badgeText = String(badgeValue);
        tab.badge = badgeValue;
        if (existingBadge) {
            dom.setText(existingBadge, badgeText);
            return;
        }
        const tabElement = options.resolveElement(`#${options.tabId}-tab`);
        if (!tabElement) {
            return;
        }
        const badgeNode = dom.create('span', { className: 'tab-notify-badge', id: `${options.tabId}-badge` });
        dom.setText(badgeNode, badgeText);
        dom.appendChild(tabElement, badgeNode);
        return;
    }

    delete tab.badge;
    if (existingBadge) {
        dom.remove(existingBadge);
    }
};

const updateTabNotifyBadge = (options: TabNotifyBadgeUpdateOptions): void => {
    const tab = findTabById(options.tabs, options.tabId);
    if (!tab) {
        return;
    }

    if (options.count > 0) {
        const displayCount = resolveNotifyBadgeText(options.count);
        tab.notifyBadge = displayCount;
        const badgeElement = options.resolveElement(`#${options.tabId}-notify`);
        if (badgeElement) {
            dom.setText(badgeElement, displayCount);
            dom.setAttribute(badgeElement, 'aria-label', `${options.count} notifications`);
            return;
        }
        const tabElement = options.resolveElement(`#${options.tabId}-tab`);
        if (!tabElement) {
            return;
        }
        const notifyBadge = dom.create('span', {
            className: 'tab-notify-badge',
            id: `${options.tabId}-notify`
        });
        dom.setText(notifyBadge, displayCount);
        dom.setAttribute(notifyBadge, 'aria-label', `${options.count} notifications`);
        dom.appendChild(tabElement, notifyBadge);
        return;
    }

    delete tab.notifyBadge;
    const badgeElement = options.resolveElement(`#${options.tabId}-notify`);
    if (badgeElement) {
        dom.remove(badgeElement);
    }
};

const clearNotifyBadges = (tabs: TabConfig[], resolveElement: ResolveTabElement): void => {
    tabs.forEach((tab) => {
        delete tab.notifyBadge;
        const badgeElement = resolveElement(`#${tab.id}-notify`);
        if (badgeElement) {
            dom.remove(badgeElement);
        }
    });
};

export { clearNotifyBadges, resolveActiveTabAfterRemoval, setRightButtonVisibility, setTabDisabled, updateTabBadge, updateTabNotifyBadge };
