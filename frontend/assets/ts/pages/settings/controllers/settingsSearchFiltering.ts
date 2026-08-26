/* SoAI - Settings page search filtering [frontend/assets/ts/pages/settings/controllers/settingsSearchFiltering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createSearchTextIndex, matchesSearchFilterQuery, matchSearchConfigPath } from '@core/search/searchQuery.ts';
import { isSettingItemApplicable } from '@core/settings/settingItemApplicability.ts';
import { applyFilteredTabNotifyBadges, applyFilteredTabSelection, resolveFilteredTabSelection, type FilterTabsComponent, type TabCountEntry } from '@core/ui/controls/tabs/filterState.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type SettingsTabsComponent = FilterTabsComponent;

interface SettingsSearchHost extends PageDomOwnerHost {
    searchQuery: string;
    advancedMode: boolean;
    currentSection: string;
    getData(element: Element, key: string): string | null;
    queryTabContents(): Element[];
    getEmptyStateElement(): Element | null;
    getTabsComponent(): SettingsTabsComponent | null;
    getBaselineTabNotifyCounts(): TabCountEntry[];
    applySecurityNotifyBadgeVariant(active: boolean): void;
}

const ITEM_SELECTOR = '.setting-item, .settings-record-item';
const GROUP_SELECTOR = '.settings-section, .settings-subgroup';

const collectSearchText = (host: SettingsSearchHost, item: Element): string => {
    const inputCandidate = host.pageDom.optional('input, textarea, select', item);
    const inputElement = inputCandidate instanceof HTMLInputElement || inputCandidate instanceof HTMLTextAreaElement || inputCandidate instanceof HTMLSelectElement ? inputCandidate : null;
    const labelNode = host.pageDom.optional('.setting-label, .action-title, .settings-record-label', item);
    const helpNode = host.pageDom.optional('.setting-help, .action-description, .api-key-prefix, .backup-meta, .settings-record-meta, .settings-record-badge, .settings-record-badges', item);
    return createSearchTextIndex([labelNode instanceof Node ? (labelNode.textContent ?? '') : '', helpNode instanceof Node ? (helpNode.textContent ?? '') : '', inputElement?.value ?? '', item.textContent ?? '']);
};

const matchesSettingItemQuery = (host: SettingsSearchHost, item: Element, query: string): boolean => {
    if (matchesSearchFilterQuery(collectSearchText(host, item), query)) {
        return true;
    }
    const configPath = host.getData(item, 'path');
    return configPath !== null && matchSearchConfigPath(configPath, query) !== 'none';
};

const updateSettingsEmptyState = (host: SettingsSearchHost, showAll: boolean, counts: Map<string, number>, tabContents: readonly Element[]): void => {
    const empty = host.getEmptyStateElement();
    if (!empty) return;

    if (showAll || !host.searchQuery) {
        host.pageDom.toggleClass(empty, 'u-hidden', true);
        tabContents.forEach((tabContent) => host.pageDom.toggleClass(tabContent, 'u-hidden', false));
        return;
    }

    const hasVisible = Array.from(counts.values()).some((count) => count > 0);
    host.pageDom.toggleClass(empty, 'u-hidden', hasVisible);
    tabContents.forEach((tabContent) => host.pageDom.toggleClass(tabContent, 'u-hidden', hasVisible ? false : true));
};

const updateSettingsTabBadges = (host: SettingsSearchHost, counts: Map<string, number>): void => {
    const tabsComponent = host.getTabsComponent();
    const tabCounts: TabCountEntry[] = [];
    counts.forEach((count: number, id: string) => {
        const hasResults = count > 0;
        tabCounts.push([id, count]);
        const tabElement = host.pageDom.optional(`#${id}-tab`);
        if (!tabElement) return;
        const isAdvanced = host.getData(tabElement, 'advanced') === 'true';
        if (isAdvanced && !host.advancedMode) {
            host.pageDom.toggleClass(tabElement, 'u-hidden', true);
            return;
        }

        if (host.searchQuery) {
            host.pageDom.toggleClass(tabElement, 'u-hidden', !hasResults);
        } else {
            host.pageDom.toggleClass(tabElement, 'u-hidden', false);
        }
    });
    const searchActive = host.searchQuery.length > 0;
    applyFilteredTabNotifyBadges(tabsComponent, tabCounts, searchActive);
    if (!searchActive) {
        applyFilteredTabNotifyBadges(tabsComponent, host.getBaselineTabNotifyCounts(), true);
    }
    host.applySecurityNotifyBadgeVariant(!searchActive);
    applyFilteredTabSelection(tabsComponent, resolveFilteredTabSelection(tabCounts, host.currentSection), searchActive);
};

const filterSettingsPage = (host: SettingsSearchHost): void => {
    const activeContent = host.pageDom.optional('.tab-content.is-active');
    if (!activeContent) return;

    const query = host.searchQuery;
    const showAll = !query;
    const counts = new Map<string, number>();
    const tabContents = host.queryTabContents();

    tabContents.forEach((tabContent) => {
        const tabId = tabContent.id.replace('-content', '');
        const isAdvanced = host.getData(tabContent, 'tabType') === 'advanced';
        if (isAdvanced && !host.advancedMode) {
            counts.set(tabId, 0);
            return;
        }

        let matches = 0;
        host.pageDom.query(ITEM_SELECTOR, tabContent).forEach((item) => {
            if (!isSettingItemApplicable(item)) {
                host.pageDom.toggleClass(item, 'u-hidden', true);
                return;
            }
            const visible = showAll || matchesSettingItemQuery(host, item, query);
            host.pageDom.toggleClass(item, 'u-hidden', !visible);
            if (visible && !showAll) matches++;
        });

        host.pageDom.query(GROUP_SELECTOR, tabContent).forEach((group) => {
            const items = host.pageDom.query(ITEM_SELECTOR, group);
            if (items.length === 0) {
                host.pageDom.toggleClass(group, 'u-hidden', !showAll);
                return;
            }
            const hasVisible = items.some((item) => !item.classList.contains('u-hidden'));
            host.pageDom.toggleClass(group, 'u-hidden', !hasVisible);
        });

        counts.set(tabId, matches);
    });

    updateSettingsTabBadges(host, counts);
    updateSettingsEmptyState(host, showAll, counts, tabContents);
};

export { filterSettingsPage, updateSettingsEmptyState, updateSettingsTabBadges };
export type { SettingsSearchHost };
