/* SoAI - Shared UI filter state [frontend/assets/ts/core/ui/controls/tabs/filterState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface FilterTabsComponent {
    updateTabNotifyBadge?: (id: string, count: number) => void;
    clearNotifyBadges?: () => void;
    setActiveTab?: (id: string) => void;
}

type TabCountEntry = readonly [string, number];

interface FilteredTabSelection {
    activeTabHasResults: boolean;
    firstTabId: string | null;
}

const clearFilteredTabNotifyBadges = (tabsComponent: FilterTabsComponent | null, tabIds: readonly string[]): void => {
    if (!tabsComponent) {
        return;
    }
    if (tabsComponent.clearNotifyBadges) {
        tabsComponent.clearNotifyBadges();
        return;
    }
    for (const tabId of tabIds) {
        tabsComponent.updateTabNotifyBadge?.(tabId, 0);
    }
};

const applyFilteredTabNotifyBadges = (tabsComponent: FilterTabsComponent | null, counts: readonly TabCountEntry[], showCounts: boolean): void => {
    if (!tabsComponent?.updateTabNotifyBadge) {
        return;
    }
    for (const [tabId, count] of counts) {
        tabsComponent.updateTabNotifyBadge(tabId, showCounts && count > 0 ? count : 0);
    }
};

const resolveFilteredTabSelection = (counts: readonly TabCountEntry[], currentTabId: string): FilteredTabSelection => {
    let firstTabId: string | null = null;
    let activeTabHasResults = false;
    for (const [tabId, count] of counts) {
        if (count <= 0) {
            continue;
        }
        if (firstTabId === null) {
            firstTabId = tabId;
        }
        if (tabId === currentTabId) {
            activeTabHasResults = true;
        }
    }
    return { activeTabHasResults, firstTabId };
};

const applyFilteredTabSelection = (tabsComponent: FilterTabsComponent | null, selection: FilteredTabSelection, searchActive: boolean): void => {
    if (!searchActive || selection.activeTabHasResults || !selection.firstTabId) {
        return;
    }
    tabsComponent?.setActiveTab?.(selection.firstTabId);
};

export { applyFilteredTabNotifyBadges, applyFilteredTabSelection, clearFilteredTabNotifyBadges, resolveFilteredTabSelection };
export type { FilterTabsComponent, TabCountEntry };
