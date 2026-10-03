/* SoAI - Settings page control layer rendering [frontend/assets/ts/pages/settings/controllers/page/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { createFormManager, getFormManager } from '@core/formService.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveSettingsConfigPathFromQuery } from '@core/settings/configPathDeepLink.ts';
import type { GenerateStandardHeaderOptions } from '@core/routing/pages/pagetypes/public.ts';
import { buildQueryRoute } from '@core/routing/router/events.ts';
import { IN_PLACE_SEARCH_DEBOUNCE_MS } from '@core/search/searchDebounce.ts';
import { normalizeSearchMatchQuery } from '@core/search/searchQuery.ts';
import type { RenderContext } from '@core/StaticBasePage.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import type { TabCountEntry } from '@core/ui/controls/tabs/filterState.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { UI_IDS } from '@features/settings/public.ts';
import type { SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import { getElement, syncSettingsSectionActivity } from '@pages/settings/controllers/page/service.ts';
import { applySecurityNotifyBadgeVariant, resolveSecurityFindingCount, SECURITY_TAB_ID } from '@pages/settings/controllers/page/securityTabBadgeController.ts';
import { createAllTabs, createEmptyStateElement, materializeAdvancedSettings, renderAllContent, updateTabsVisibility } from '@pages/settings/controllers/page/settingsTabsController.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';
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
const applyAdvancedModeChange = async (page: SettingsRuntimeContext, state: SettingsPageState, rebindConfigForm: () => void): Promise<void> => {
    page.owners.storage.setAdvancedMode(state.advancedMode);
    const title = page.owners.pageDom.optional('.page-header-title');
    const button = getElement(page, state, UI_IDS.ADVANCED_TOGGLE_BTN);
    setModeAwareText(page, title, state.advancedMode, i18n.t('settings.advancedTitle'), i18n.t('settings.title'));
    updateAdvancedToggleButton(page, button, state.advancedMode);
    if (state.advancedMode && (await materializeAdvancedSettings(page, state))) {
        rebindConfigForm();
    }
    updateTabsVisibility(page, state);
    if (page.controls.getSearchQuery()?.trim()) {
        filterSettings(page, state);
    }
};
const onTabChange = (page: SettingsRuntimeContext, state: SettingsPageState, newTab: string): void => {
    if (!isString(newTab) || !newTab) {
        throw new TypeError('Settings tab change requires a non-empty tab id');
    }
    state.currentSection = newTab;
    syncSettingsSectionActivity(state, newTab);
    const currentQueryParameters = page.owners.router.getQueryParameters();
    page.owners.router.replaceCurrentRoute(buildQueryRoute('settings', { ...currentQueryParameters, tab: newTab }));
    page.owners.pageDom.query('.tab-content').forEach((tabContent) => {
        if (!(tabContent instanceof HTMLElement)) {
            throw new TypeError('Settings tab content must be an HTMLElement');
        }
        page.owners.pageDom.toggleClass(tabContent, 'is-active', tabContent.id === `${newTab}-content`);
    });
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
