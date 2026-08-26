/* SoAI - Shared UI tabs [frontend/assets/ts/core/ui/controls/Tabs.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { BaseComponent } from '@core/BaseComponent.ts';
import { dom } from '@core/dom/dom.ts';
import { clearNotifyBadges, resolveActiveTabAfterRemoval, setRightButtonVisibility, setTabDisabled, updateTabBadge, updateTabNotifyBadge } from '@core/ui/controls/tabs/actions.ts';
import { cacheTabsDomReferences, renderRightButtons, scrollTabIntoView, setupOverflowNav, updateActiveTabState } from '@core/ui/controls/tabs/effects.ts';
import { findRightButtonConfig, normalizeTabsOptions } from '@core/ui/controls/tabs/service.ts';
import type { RightButtonConfig, TabConfig, TabsOptions } from '@core/ui/controls/tabs/types.ts';
import { renderContainerMarkup } from '@core/ui/controls/tabs/view.ts';
import type { OverflowNavController } from '@core/ui/controls/OverflowNav.ts';

const DEFAULT_TABS_OPTIONS: TabsOptions = {
    tabs: [],
    rightButtons: {},
    activeTab: null,
    onTabChange: null,
    className: 'tabs',
    enableOverflowNav: true,
    navScrollAmount: 0.8
};

class TabsComponent extends BaseComponent<TabsOptions> {
    activeTab: string | null;
    tabs: TabConfig[];
    rightButtons: Record<string, RightButtonConfig[]>;
    onTabChange: ((activeTab: string, previousTab: string | null) => void) | null;
    nav: HTMLElement | null;
    leftNavButton: HTMLElement | null;
    rightNavButton: HTMLElement | null;
    buttonsContainer: HTMLElement | null;
    enableOverflowNav: boolean;
    navScrollAmount: number;
    overflowNav: OverflowNavController | null;

    constructor(element: HTMLElement, options: TabsOptions = {}) {
        super(element, options, DEFAULT_TABS_OPTIONS);
        this.activeTab = null;
        this.tabs = [];
        this.rightButtons = {};
        this.onTabChange = null;
        this.nav = null;
        this.leftNavButton = null;
        this.rightNavButton = null;
        this.buttonsContainer = null;
        this.enableOverflowNav = true;
        this.navScrollAmount = 0.8;
        this.overflowNav = null;
    }

    override get options(): TabsOptions {
        return super.options;
    }

    override set options(value: TabsOptions) {
        super.options = value;
    }

    override async onInitialize(): Promise<void> {
        const normalizedOptions = normalizeTabsOptions(this.options);
        this.tabs = normalizedOptions.tabs;
        this.rightButtons = normalizedOptions.rightButtons;
        this.onTabChange = normalizedOptions.onTabChange;
        this.activeTab = normalizedOptions.activeTab;
        this.enableOverflowNav = normalizedOptions.enableOverflowNav;
        this.navScrollAmount = normalizedOptions.navScrollAmount;
        this.render();
    }

    private getClassName(): string {
        return this.options.className ?? 'tabs';
    }

    render(): void {
        if (!this.element) {
            return;
        }
        this.overflowNav?.dispose();
        this.overflowNav = null;
        const className = this.getClassName();
        dom.setHTML(this.element, renderContainerMarkup(className, this.tabs, this.activeTab, this.rightButtons, this.enableOverflowNav), { escape: false });

        this.cacheDomReferences();
        this.updateActiveTab();
        this.updateRightButtons();
        this.setupOverflowMonitoring();
        if (this.activeTab) {
            this.scrollTabIntoView(this.activeTab);
        }
    }

    cacheDomReferences(): void {
        const refs = cacheTabsDomReferences((selector) => this.getUI(selector), this.getClassName());
        this.nav = refs.nav;
        this.leftNavButton = refs.leftNavButton;
        this.rightNavButton = refs.rightNavButton;
        this.buttonsContainer = refs.buttonsContainer;
    }

    override bindEvents(): void {
        if (!this.element) {
            return;
        }

        const className = this.getClassName();

        this.addEventListener(this.element, 'click', (event: Event) => {
            const target = event.target instanceof Element ? event.target : null;
            if (!target) {
                return;
            }

            const tabButton = target.closest(`.${className}-tab`);
            if (tabButton) {
                const tabId = dom.getData(tabButton, 'tab');
                if (tabId) {
                    this.setActiveTab(tabId);
                }
            }

            const rightButton = target.closest(`.${className}-buttons .ui-button`);
            if (rightButton) {
                this.handleRightButtonClick(rightButton.id);
            }
        });
    }

    setActiveTab(tabId: string): void {
        if (this.activeTab === tabId) {
            return;
        }

        const previousTab = this.activeTab;
        this.activeTab = tabId;

        this.updateActiveTab();
        this.updateRightButtons();
        this.scrollTabIntoView(tabId);
        this.overflowNav?.update();

        this.emit('tabChange', { activeTab: this.activeTab, previousTab });
        this.onTabChange?.(this.activeTab, previousTab);
    }

    updateActiveTab(): void {
        updateActiveTabState((selector) => this.$$(selector), this.getClassName(), this.activeTab);
    }

    updateRightButtons(): void {
        this.buttonsContainer = renderRightButtons({
            className: this.getClassName(),
            activeTab: this.activeTab,
            rightButtons: this.rightButtons,
            buttonsContainer: this.buttonsContainer,
            resolveElement: (selector) => this.getUI(selector)
        });
    }

    handleRightButtonClick(buttonId: string): void {
        const buttonConfig = findRightButtonConfig(buttonId, this.activeTab, this.rightButtons);
        buttonConfig?.action?.();
    }

    setupOverflowMonitoring(): void {
        this.overflowNav = setupOverflowNav({
            enableOverflowNav: this.enableOverflowNav,
            navScrollAmount: this.navScrollAmount,
            nav: this.nav,
            leftNavButton: this.leftNavButton,
            rightNavButton: this.rightNavButton,
            addEventListener: (target, event, handler, options) => this.addEventListener(target, event, handler, options)
        });
    }

    scrollTabIntoView(tabId: string): void {
        scrollTabIntoView(this.nav, tabId, (selector) => this.getUI(selector));
    }

    updateOverflowState(): void {
        this.overflowNav?.update();
    }

    getActiveTab(): string | null {
        return this.activeTab;
    }

    addTab(tab: TabConfig): void {
        this.tabs.push(tab);
        this.render();
    }

    removeTab(tabId: string): void {
        this.tabs = this.tabs.filter((tab) => tab.id !== tabId);
        this.activeTab = resolveActiveTabAfterRemoval(this.tabs, this.activeTab, tabId);
        this.render();
    }

    setRightButtons(tabId: string, buttons: RightButtonConfig[]): void {
        this.rightButtons[tabId] = buttons;
        if (this.activeTab === tabId) {
            this.updateRightButtons();
        }
    }

    updateTabBadge(tabId: string, badge: string | number | null | undefined): void {
        updateTabBadge({
            tabId,
            badge,
            tabs: this.tabs,
            resolveElement: (selector) => this.getUI(selector)
        });
    }

    updateTabNotifyBadge(tabId: string, count: number): void {
        updateTabNotifyBadge({
            tabId,
            count,
            tabs: this.tabs,
            resolveElement: (selector) => this.getUI(selector)
        });
    }

    clearNotifyBadges(): void {
        clearNotifyBadges(this.tabs, (selector) => this.getUI(selector));
    }

    private setTabDisabledState(tabId: string, isDisabled: boolean): void {
        setTabDisabled({
            tabId,
            isDisabled,
            activeTab: this.activeTab,
            tabs: this.tabs,
            resolveElement: (selector) => this.getUI(selector),
            activateTab: (activeTabId) => this.setActiveTab(activeTabId)
        });
    }

    enableTab(tabId: string): void {
        this.setTabDisabledState(tabId, false);
    }

    disableTab(tabId: string): void {
        this.setTabDisabledState(tabId, true);
    }

    showRightButton(buttonId: string): void {
        setRightButtonVisibility((selector) => this.getUI(selector), buttonId, true);
    }

    hideRightButton(buttonId: string): void {
        setRightButtonVisibility((selector) => this.getUI(selector), buttonId, false);
    }

    override async onDestroy(): Promise<void> {
        this.overflowNav?.dispose();
        this.overflowNav = null;
        await super.onDestroy();
    }
}

export { TabsComponent };
