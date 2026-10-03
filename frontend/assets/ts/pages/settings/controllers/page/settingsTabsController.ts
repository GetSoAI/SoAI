/* SoAI - Settings tab creation, lazy advanced materialization, and content rendering [frontend/assets/ts/pages/settings/controllers/page/settingsTabsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { resolveTabFromQuery } from '@core/queryTabs.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { UI_IDS } from '@features/settings/public.ts';
import { isNormalTabVisible } from '@pages/settings/controllers/page/settingsAccessController.ts';
import type { SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import { renderNormalTabContent } from '@pages/settings/controllers/page/normalTabRendering.ts';
import { getElement, resetElementCache, resolveAdvancedRenderer } from '@pages/settings/controllers/page/service.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';
import { applySettingsTabTones } from '@pages/settings/controllers/page/tabToneController.ts';

const getNormalTabs = (page: SettingsRuntimeContext, state: SettingsPageState) => page.edition.normalTabs.filter((definition) => isNormalTabVisible(page, state, definition));

const prepareAdvancedTabs = (state: SettingsPageState): void => {
    if (!state.advancedAccessEnabled || state.advancedStructure !== null) {
        return;
    }
    const renderer = resolveAdvancedRenderer(state);
    const structure = renderer.analyze(state.coreConfig);
    const tabs = renderer.createTabs(structure);
    state.advancedStructure = structure;
    state.advancedTabs = tabs;
};

const initializeSettingsTabs = async (page: SettingsRuntimeContext, state: SettingsPageState): Promise<void> => {
    const tabs = [...getNormalTabs(page, state), ...state.advancedTabs];
    const rightButtons: Record<string, []> = {};
    tabs.forEach((tab) => {
        rightButtons[tab.id] = [];
    });
    const tabsComponent = page.owners.layout.initializeTabs(UI_IDS.TAB_CONTAINER, {
        tabs: tabs.map((tab) => ('label' in tab ? { id: tab.id, label: tab.label } : { id: tab.id, label: tab.getLabel() })),
        rightButtons,
        activeTab: state.currentSection,
        className: 'tabs'
    });
    await tabsComponent?.initialize();
    page.owners.pageDom.flush();
    applySettingsTabTones(page, state);
    updateTabsVisibility(page, state);
    page.owners.layout.queueResponsive();
};

const createAllTabs = async (page: SettingsRuntimeContext, state: SettingsPageState): Promise<void> => {
    if (state.advancedMode) {
        prepareAdvancedTabs(state);
    } else {
        state.advancedStructure = null;
        state.advancedTabs = [];
    }
    const normalTabs = getNormalTabs(page, state);
    const firstTab = normalTabs[0];
    if (!firstTab) {
        throw new Error('No normal tab definitions found');
    }
    const tabIds = [...normalTabs, ...state.advancedTabs].map((tab) => tab.id);
    const tabFromQuery = resolveTabFromQuery(state.initialRouteParameters, tabIds);
    const requestedIsAdvanced = tabFromQuery ? state.advancedTabs.some((definition) => definition.id === tabFromQuery) : false;
    state.currentSection = tabFromQuery && (!requestedIsAdvanced || state.advancedMode) ? tabFromQuery : firstTab.id;
    await initializeSettingsTabs(page, state);
};

const renderNormalTabsContent = (page: SettingsRuntimeContext, state: SettingsPageState): string => {
    return getNormalTabs(page, state)
        .map((definition) => {
            const content = renderNormalTabContent(state, definition);
            const isActive = state.currentSection === definition.id;
            return `<div class="tab-content${isActive ? ' is-active' : ''}" id="${definition.id}-content" data-tab-type="normal">${content}</div>`;
        })
        .join('');
};

const renderAdvancedTabsContent = (state: SettingsPageState): DocumentFragment | null => {
    if (state.advancedStructure === null) {
        return null;
    }
    return resolveAdvancedRenderer(state).render(state.advancedStructure, { activeTabId: state.currentSection });
};

const createEmptyStateElement = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    const container = getElement(page, state, UI_IDS.CONTENT);
    if (!container) {
        return;
    }
    const element = page.owners.pageElements.createElement('div');
    element.id = UI_IDS.EMPTY_STATE;
    page.owners.pageDom.addClass(element, ['settings-empty', 'u-hidden']);
    page.owners.pageDom.updateHtml(
        element,
        renderEmptyState({
            icon: page.owners.services.getIconSync('search', { size: 48, strokeWidth: 1.5 }),
            title: i18n.t('settings.noSettingsFound'),
            message: i18n.t('settings.noSettingsFoundDescription')
        })
    );
    page.owners.pageDom.append(container, element);
};

const renderAllContent = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    const container = getElement(page, state, UI_IDS.CONTENT);
    if (!container) {
        return;
    }
    const fragment = page.owners.dom.createFragment();
    const normalContent = renderNormalTabsContent(page, state);
    if (normalContent) {
        fragment.appendChild(page.owners.dom.createFragment(toTrustedUiHtml(normalContent)));
    }
    const advancedContent = renderAdvancedTabsContent(state);
    if (advancedContent?.childNodes.length) {
        fragment.appendChild(advancedContent);
    }
    resetElementCache(state);
    page.owners.pageDom.replaceContent(container, fragment, { escape: false });
    createEmptyStateElement(page, state);
    updateTabsVisibility(page, state);
};

const materializeAdvancedSettings = async (page: SettingsRuntimeContext, state: SettingsPageState): Promise<boolean> => {
    if (!state.advancedAccessEnabled || state.advancedStructure !== null) {
        return false;
    }
    const container = getElement(page, state, UI_IDS.CONTENT);
    if (!container) {
        throw new Error('Advanced settings content container is required');
    }
    prepareAdvancedTabs(state);
    const advancedContent = renderAdvancedTabsContent(state);
    if (advancedContent === null) {
        throw new Error('Advanced settings content could not be materialized');
    }
    const hasAdvancedContent = advancedContent.childNodes.length > 0;
    if (hasAdvancedContent) {
        const emptyState = getElement(page, state, UI_IDS.EMPTY_STATE);
        if (emptyState) {
            page.owners.pageDom.insertBefore(container, advancedContent, emptyState);
        } else {
            page.owners.pageDom.append(container, advancedContent);
        }
        resetElementCache(state);
    }
    await initializeSettingsTabs(page, state);
    return hasAdvancedContent;
};

const updateTabsVisibility = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    if (!state.advancedAccessEnabled) {
        return;
    }
    page.owners.pageDom.query('.tabs-tab').forEach((tab) => {
        if (page.owners.dom.getData(tab, 'advanced') === 'true') {
            page.owners.pageDom.toggleClass(tab, 'u-hidden', !state.advancedMode);
        }
    });
    if (!state.advancedMode && state.advancedTabs.some((tab) => tab.id === state.currentSection)) {
        const firstTab = getNormalTabs(page, state)[0];
        if (!firstTab) {
            throw new Error('No normal tab definitions found');
        }
        page.owners.layout.getTabs()?.setActiveTab(firstTab.id);
    }
};

export { createAllTabs, createEmptyStateElement, materializeAdvancedSettings, renderAllContent, updateTabsVisibility };
