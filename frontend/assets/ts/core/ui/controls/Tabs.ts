/* SoAI - Shared UI tabs [frontend/assets/ts/core/ui/controls/Tabs.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { BaseComponent } from '@core/BaseComponent.ts';
import { dom } from '@core/dom/dom.ts';
import { clearNotifyBadges, resolveActiveTabAfterRemoval, setRightButtonVisibility, setTabDisabled, updateTabBadge, updateTabNotifyBadge } from '@core/ui/controls/tabs/actions.ts';
import { renderRightButtons, resolveTabsNav, scrollTabIntoView, updateActiveTabState } from '@core/ui/controls/tabs/effects.ts';
import { findRightButtonConfig, normalizeTabsOptions } from '@core/ui/controls/tabs/service.ts';
import type { RightButtonConfig, TabConfig, TabsOptions } from '@core/ui/controls/tabs/types.ts';
import { renderContainerMarkup } from '@core/ui/controls/tabs/view.ts';

const DEFAULT_TABS_OPTIONS: TabsOptions = {
    tabs: [],
    rightButtons: {},
    activeTab: null,
    onTabChange: null,
    className: 'tabs'
};

class TabsComponent extends BaseComponent<TabsOptions> {
    activeTab: string | null;
    tabs: TabConfig[];
    rightButtons: Record<string, RightButtonConfig[]>;
    onTabChange: ((activeTab: string, previousTab: string | null) => void) | null;
    nav: HTMLElement | null;
    buttonsContainer: HTMLElement | null;

    constructor(element: HTMLElement, options: TabsOptions = {}) {
        super(element, options, DEFAULT_TABS_OPTIONS);
        this.activeTab = null;
        this.tabs = [];
        this.rightButtons = {};
        this.onTabChange = null;
        this.nav = null;
        this.buttonsContainer = null;
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
        this.render();
    }

    private getClassName(): string {
        return this.options.className ?? 'tabs';
    }

    render(): void {
        if (!this.element) {
            return;
        }
        const className = this.getClassName();
        dom.setHTML(this.element, renderContainerMarkup(className, this.tabs, this.activeTab, this.rightButtons), { escape: false });

        this.nav = resolveTabsNav((selector) => this.getUI(selector), className);
        this.buttonsContainer = null;
        this.updateActiveTab();
        this.updateRightButtons();
        if (this.activeTab) {
            this.scrollTabIntoView(this.activeTab);
        }
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
            if (tabButton && tabButton.getAttribute('aria-disabled') !== 'true') {
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

    scrollTabIntoView(tabId: string): void {
        scrollTabIntoView(this.nav, tabId, (selector) => this.getUI(selector));
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

    updateTabNotifyBadge(tabId: string, count: number, ariaLabel?: string): void {
        updateTabNotifyBadge({
            tabId,
            count,
            ariaLabel,
            tabs: this.tabs,
            resolveElement: (selector) => this.getUI(selector)
        });
    }

    clearNotifyBadges(): void {
        clearNotifyBadges(this.tabs, (selector) => this.getUI(selector));
    }

    private setTabDisabledState(tabId: string, disabledLabel: string | null): void {
        setTabDisabled({
            tabId,
            disabledLabel,
            activeTab: this.activeTab,
            tabs: this.tabs,
            resolveElement: (selector) => this.getUI(selector),
            activateTab: (activeTabId) => this.setActiveTab(activeTabId)
        });
    }

    enableTab(tabId: string): void {
        this.setTabDisabledState(tabId, null);
    }

    disableTab(tabId: string, disabledLabel: string): void {
        this.setTabDisabledState(tabId, disabledLabel);
    }

    showRightButton(buttonId: string): void {
        setRightButtonVisibility((selector) => this.getUI(selector), buttonId, true);
    }

    hideRightButton(buttonId: string): void {
        setRightButtonVisibility((selector) => this.getUI(selector), buttonId, false);
    }
}

export { TabsComponent };
