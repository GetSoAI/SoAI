/* SoAI - Settings page control layer rendering [frontend/assets/ts/pages/settings/controllers/page/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { createFormManager, getFormManager } from '@core/formService.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveTabFromQuery } from '@core/queryTabs.ts';
import { resolveSettingsConfigPathFromQuery } from '@core/settings/configPathDeepLink.ts';
import type { GenerateStandardHeaderOptions } from '@core/routing/pages/pagetypes/public.ts';
import { buildQueryRoute } from '@core/routing/router/events.ts';
import { IN_PLACE_SEARCH_DEBOUNCE_MS } from '@core/search/searchDebounce.ts';
import { normalizeSearchMatchQuery } from '@core/search/searchQuery.ts';
import type { RenderContext } from '@core/StaticBasePage.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import type { TabCountEntry } from '@core/ui/controls/tabs/filterState.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { UI_IDS } from '@features/settings/public.ts';
import { isNormalTabVisible } from '@pages/settings/controllers/page/settingsAccessController.ts';
import type { SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import { renderNormalTabContent } from '@pages/settings/controllers/page/normalTabRendering.ts';
import { getElement, resetElementCache, resolveAdvancedRenderer } from '@pages/settings/controllers/page/service.ts';
import { applySecurityNotifyBadgeVariant, resolveSecurityFindingCount, SECURITY_TAB_ID } from '@pages/settings/controllers/page/securityTabBadgeController.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';
import { applySettingsTabTones } from '@pages/settings/controllers/page/tabToneController.ts';
import { filterSettingsPage, type SettingsSearchHost } from '@pages/settings/controllers/settingsSearchFiltering.ts';
import { setupSettingsSearch } from '@pages/settings/controllers/settingsSearchSetup.ts';
import { renderSettingsPageView } from '@pages/settings/view.ts';

const renderView = (page: SettingsRuntimeContext, state: SettingsPageState, context?: RenderContext): TrustedHtml => {
    const stateContext = context?.state;
    const advancedMode = (() => {
        if (!isObject(stateContext)) {
            return state.advancedMode;
        }
        const candidate = stateContext['advancedMode'];
        return typeof candidate === 'boolean' ? candidate : state.advancedMode;
    })();
    return renderSettingsPageView({
        generateStandardHeader: (options: GenerateStandardHeaderOptions): TrustedHtml => page.owners.layout.generateHeader({ ...options }),
        getIconSync: (name: IconName, options?: IconOptions): TrustedHtml => page.owners.services.getIconSync(name, options ? { ...options } : undefined),
        canAccessAdvanced: state.advancedAccessEnabled,
        advancedMode
    });
};
const setupNavigationGuard = (page: SettingsRuntimeContext, state: SettingsPageState, hasUnsavedChanges: () => boolean): void => {
    state.navigationGuardCleanup?.();
    const cleanup = page.owners.layout.registerUnsavedChanges({ hasUnsavedChanges, confirmMessage: i18n.t('settings.unsavedChanges'), guardId: 'settings-dirty-guard' });
    state.navigationGuardCleanup = typeof cleanup === 'function' ? cleanup : null;
};

const setModeAwareText = (page: SettingsRuntimeContext, element: Element | null, advanced: boolean, advancedText: string, basicText: string): void => {
    if (!element) {
        return;
    }
    page.owners.pageDom.updateText(element, advanced ? advancedText : basicText);
};

const updateAdvancedToggleButton = (page: SettingsRuntimeContext, button: Element | null, advanced: boolean): void => {
    if (!button) {
        return;
    }
    const label = advanced ? i18n.t('settings.basicMode') : i18n.t('settings.advancedMode');
    const labelElement = button.lastElementChild;
    page.owners.pageDom.updateText(labelElement ?? button, label);
    page.owners.pageDom.updateAttribute(button, 'aria-label', label);
    page.owners.pageDom.updateAttribute(button, 'data-tooltip', label);
};

const createEmptyStateElement = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    const container = getElement(page, state, UI_IDS.CONTENT);
    if (!container) {
        return;
    }
    const element = page.owners.pageElements.createElement('div');
    element.id = UI_IDS.EMPTY_STATE;
    page.owners.pageDom.addClass(element, ['settings-empty', 'u-hidden']);
    const emptyStateMarkup = renderEmptyState({
        icon: page.owners.services.getIconSync('search', { size: 48, strokeWidth: 1.5 }),
        title: i18n.t('settings.noSettingsFound'),
        message: i18n.t('settings.noSettingsFoundDescription')
    });
    page.owners.pageDom.updateHtml(element, emptyStateMarkup);
    page.owners.pageDom.append(container, element);
};
const createSettingsSearchHostRuntime = (page: SettingsRuntimeContext, state: SettingsPageState): SettingsSearchHost => {
    if (!state.settingsSearchHost) {
        state.settingsSearchHost = {
            pageDom: page.owners.pageDom,
            get searchQuery() {
                const query = page.controls.getSearchQuery();
                return isString(query) ? query : '';
            },
            get advancedMode() {
                return state.advancedMode;
            },
            get currentSection() {
                return state.currentSection;
            },
            getData: (element: Element, key: string): string | null => page.owners.dom.getData(element, key),
            queryTabContents: (): Element[] => page.owners.pageDom.query('.tab-content'),
            getEmptyStateElement: (): Element | null => getElement(page, state, UI_IDS.EMPTY_STATE),
            getTabsComponent: () => page.owners.layout.getTabs(),
            getBaselineTabNotifyCounts: (): TabCountEntry[] => [[SECURITY_TAB_ID, resolveSecurityFindingCount(state)]],
            applySecurityNotifyBadgeVariant: (active: boolean): void => applySecurityNotifyBadgeVariant(page, active)
        };
    }
    return state.settingsSearchHost;
};
const filterSettings = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    filterSettingsPage(createSettingsSearchHostRuntime(page, state));
};
const updateTabsVisibility = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    if (!state.advancedAccessEnabled) {
        page.owners.layout.getTabs()?.updateOverflowState?.();
        return;
    }
    page.owners.pageDom.query('.tabs-tab').forEach((tab) => {
        if (page.owners.dom.getData(tab, 'advanced') === 'true') {
            page.owners.pageDom.toggleClass(tab, 'u-hidden', !state.advancedMode);
        }
    });
    if (!state.advancedMode && page.owners.pageDom.optional('.tab-content.is-active[data-tab-type="advanced"]')) {
        const firstTab = page.owners.pageDom.optional('.tabs-tab:not([data-advanced="true"])');
        if (firstTab instanceof HTMLElement) {
            firstTab.click();
        }
    }
    page.owners.layout.getTabs()?.updateOverflowState?.();
};
const applyAdvancedModeChange = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    page.owners.storage.setAdvancedMode(state.advancedMode);
    const title = page.owners.pageDom.optional('.page-header-title');
    const button = getElement(page, state, UI_IDS.ADVANCED_TOGGLE_BTN);
    setModeAwareText(page, title, state.advancedMode, i18n.t('settings.advancedTitle'), i18n.t('settings.title'));
    updateAdvancedToggleButton(page, button, state.advancedMode);
    updateTabsVisibility(page, state);
    filterSettings(page, state);
};
const onTabChange = (page: SettingsRuntimeContext, state: SettingsPageState, newTab: string): void => {
    if (!isString(newTab) || !newTab) {
        throw new TypeError('Settings tab change requires a non-empty tab id');
    }
    state.currentSection = newTab;
    const currentQueryParameters = page.owners.router.getQueryParameters();
    page.owners.router.replaceCurrentRoute(buildQueryRoute('settings', { ...currentQueryParameters, tab: newTab }));
    page.owners.pageDom.query('.tab-content').forEach((tabContent) => {
        if (!(tabContent instanceof HTMLElement)) {
            throw new TypeError('Settings tab content must be an HTMLElement');
        }
        page.owners.pageDom.toggleClass(tabContent, 'is-active', tabContent.id === `${newTab}-content`);
    });
    filterSettings(page, state);
    page.owners.layout.queueResponsive();
};
const requireSettingsSearchContainer = (page: SettingsRuntimeContext): HTMLElement => page.owners.pageDom.requireHTMLElement(`#${UI_IDS.SEARCH_CONTAINER}`);
const resolveSettingsSearchInput = (page: SettingsRuntimeContext, container: HTMLElement): HTMLInputElement | null => {
    const input = page.owners.dom.resolve('input.searchbar-input', container);
    return input instanceof HTMLInputElement ? input : null;
};
const setupSearch = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    setupSettingsSearch({
        pageResources: page.owners.pageResources,
        requireSearchContainer: (): HTMLElement => requireSettingsSearchContainer(page),
        isSearchInitialized: (container: HTMLElement): boolean => page.owners.pageDom.getDataAttribute(container, 'searchInitialized') === 'true',
        createStandardSearch: (container: HTMLElement, onSearch: (query: string) => void): { input: HTMLInputElement } =>
            page.owners.layout.createSearch(container, {
                placeholder: i18n.t('settings.searchPlaceholder'),
                debounceTime: IN_PLACE_SEARCH_DEBOUNCE_MS,
                onSearch
            }),
        resolveExistingInput: (container: HTMLElement): HTMLInputElement | null => resolveSettingsSearchInput(page, container),
        setSearchQuery: (query: string): void => {
            page.controls.setSearchQuery(query);
        },
        filterSettings: (): void => {
            filterSettings(page, state);
        }
    });
};
const applyConfigPathDeepLink = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    const configPath = resolveSettingsConfigPathFromQuery(state.initialRouteParameters);
    if (configPath === null) {
        return;
    }
    const input = resolveSettingsSearchInput(page, requireSettingsSearchContainer(page));
    if (!input) {
        throw new Error('Settings search input is missing');
    }
    page.owners.pageDom.updateProperty(input, 'value', configPath);
    page.controls.setSearchQuery(normalizeSearchMatchQuery(configPath));
    filterSettings(page, state);
};
const createAllTabs = async (page: SettingsRuntimeContext, state: SettingsPageState): Promise<void> => {
    const allowAdvanced = state.advancedAccessEnabled;
    const normalTabs = page.edition.normalTabs.filter((definition) => isNormalTabVisible(page, state, definition));
    if (allowAdvanced) {
        const renderer = resolveAdvancedRenderer(state);
        const structure = renderer.analyze(state.coreConfig);
        state.advancedStructure = structure;
        state.advancedTabs = renderer.createTabs(structure);
    } else {
        state.advancedStructure = null;
        state.advancedTabs = [];
    }
    const allTabs = allowAdvanced ? [...normalTabs, ...state.advancedTabs] : normalTabs;
    const firstTab = normalTabs[0];
    if (!firstTab) {
        throw new Error('No normal tab definitions found');
    }
    const tabIds = allTabs.map((tab) => tab.id);
    const tabFromQuery = resolveTabFromQuery(state.initialRouteParameters, tabIds);
    const requestedIsAdvanced = tabFromQuery ? state.advancedTabs.some((definition) => definition.id === tabFromQuery) : false;
    state.currentSection = tabFromQuery && (!requestedIsAdvanced || state.advancedMode) ? tabFromQuery : firstTab.id;
    const rightButtons: Record<string, []> = {};
    allTabs.forEach((tab) => {
        rightButtons[tab.id] = [];
    });
    page.owners.layout.initializeTabs(UI_IDS.TAB_CONTAINER, { tabs: allTabs.map((tab) => ('label' in tab ? { id: tab.id, label: tab.label } : { id: tab.id, label: tab.getLabel() })), rightButtons, activeTab: state.currentSection, className: 'tabs' });
    const raf = getRequestAnimationFrame();
    raf(() => {
        applySettingsTabTones(page, state);
        updateTabsVisibility(page, state);
    });
    page.owners.layout.queueResponsive();
};
const renderNormalTabsContent = (page: SettingsRuntimeContext, state: SettingsPageState): string => {
    return page.edition.normalTabs
        .filter((definition) => isNormalTabVisible(page, state, definition))
        .map((definition) => {
            const { id } = definition;
            const content = renderNormalTabContent(state, definition);
            const isActive = state.currentSection === id;
            return `<div class="tab-content${isActive ? ' is-active' : ''}" id="${id}-content" data-tab-type="normal">${content}</div>`;
        })
        .join('');
};
const renderAdvancedTabsContent = (state: SettingsPageState): DocumentFragment | null => {
    if (!state.advancedAccessEnabled) {
        return null;
    }
    const renderer = resolveAdvancedRenderer(state);
    if (!state.advancedStructure) {
        state.advancedStructure = renderer.analyze(state.coreConfig);
    }
    if (!state.advancedTabs.length) {
        state.advancedTabs = renderer.createTabs(state.advancedStructure);
    }
    return renderer.render(state.advancedStructure, { activeTabId: state.currentSection });
};
const renderAllContent = (page: SettingsRuntimeContext, state: SettingsPageState): void => {
    const container = getElement(page, state, UI_IDS.CONTENT);
    if (!container) {
        return;
    }
    const fragment = page.owners.dom.createFragment();
    const normalContent = renderNormalTabsContent(page, state);
    if (normalContent) {
        const normalContentMarkup = toTrustedUiHtml(normalContent);
        fragment.appendChild(page.owners.dom.createFragment(normalContentMarkup));
    }
    if (state.advancedAccessEnabled) {
        const advancedContent = renderAdvancedTabsContent(state);
        if (advancedContent && advancedContent.childNodes && advancedContent.childNodes.length) {
            fragment.appendChild(advancedContent);
        }
    }
    resetElementCache(state);
    page.owners.pageDom.replaceContent(container, fragment, { escape: false });
    createEmptyStateElement(page, state);
    updateTabsVisibility(page, state);
};
const setupFormIntegration = (page: SettingsRuntimeContext, state: SettingsPageState, onChanged: (path: string, valid: boolean) => void): void => {
    if (!state.configManager) {
        return;
    }
    const containerCandidate = getElement(page, state, UI_IDS.CONTENT);
    if (!containerCandidate) {
        return;
    }
    const container = narrowHTMLElement(containerCandidate, 'Settings content container');
    const existing = getFormManager(UI_IDS.CONTENT);
    const manager = existing ?? createFormManager(container);
    manager.cleanup();
    manager.bindToConfiguration(state.configManager);
    manager.onChange((data) => onChanged(data.path, data.valid));
};
export { applyAdvancedModeChange, applyConfigPathDeepLink, createAllTabs, createEmptyStateElement, filterSettings, onTabChange, renderAllContent, renderView, setupFormIntegration, setupNavigationGuard, setupSearch, updateTabsVisibility };
