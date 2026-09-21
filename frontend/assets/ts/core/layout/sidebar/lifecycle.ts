/* SoAI - Shared layout lifecycle [frontend/assets/ts/core/layout/sidebar/lifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dispatchCustomEvent } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { getLayoutRuntimeManager } from '@core/runtime/LayoutManager.ts';
import { SIDEBAR_DESTROYED_EVENT, SIDEBAR_READY_EVENT } from '@core/layout/sidebar/actions.ts';
import { bindSidebarLogoNavigation, bindSidebarNavigation, bindSidebarToggleHandlers, type SidebarInteractionsHost } from '@core/layout/sidebar/interactions.ts';
import type { SidebarDisposerCandidate } from '@core/layout/sidebar/disposers.ts';
import { resetSidebarBodyState } from '@core/layout/sidebar/stateUi.ts';
import type { SidebarConfigEntry } from '@core/layout/sidebar/view.ts';

interface SidebarLifecycleDomPort {
    cacheDom: () => void;
    getDomRef: (key: string) => HTMLElement | null;
    getMenuElement: () => HTMLElement | null;
    cleanupMenu: () => void;
}

interface SidebarLifecycleSessionPort {
    flushSessionDisposers: () => void;
    captureAuthSnapshot: () => Promise<void>;
    on: (target: EventTarget | Element, eventName: string, handler: (event: Event) => void) => () => void;
    addSessionDisposer: (functionValue: SidebarDisposerCandidate) => () => void;
}

interface SidebarLifecyclePresentationPort {
    setupResponsive: () => void;
    refreshPluginIndicatorFromStorage: () => Promise<void>;
    updateStateUI: () => void;
    compactSidebar: () => void;
    isExpanded: () => boolean;
    navigateTo: (pageId: string) => void;
    refreshSidebar: (options?: { syncRoute?: boolean }) => Promise<void>;
    updatePluginIndicator: () => void;
    updateAutomationRunningIndicator: () => void;
    handleResize: () => void;
    syncWithCurrentRoute: () => void;
}

interface SidebarLifecycleSubscriptionPort {
    updateBusyIndicators: () => void;
    setupChatCompletionWatcher: () => void;
    setupChatStreamingWatcher: () => void;
    setupTaskBusyWatcher: () => void;
    setupAutomationRunWatcher: () => void;
    setupLanguageListener: () => void;
    setupSidebarCustomizationListener: () => void;
    setupFirstRunListener: () => void;
    setupAuthListener: () => void;
    initializeVersionSources: () => void;
    clearBusyIndicators: () => void;
    destroyVersionController: () => void;
}

interface SidebarLifecycleRuntimePort {
    initializeModelDependentNavigation: () => Promise<void>;
    cleanupModelDependentNavigation: () => void;
    updateInitialized: (value: boolean) => void;
    getInstanceId: () => string | null;
    cleanupResources: () => Promise<void>;
}

interface SidebarLifecycleDependencies {
    dom: SidebarLifecycleDomPort;
    session: SidebarLifecycleSessionPort;
    presentation: SidebarLifecyclePresentationPort;
    subscriptions: SidebarLifecycleSubscriptionPort;
    runtime: SidebarLifecycleRuntimePort;
}

interface SidebarRefreshDependencies {
    getVisibleConfig: () => SidebarConfigEntry[];
    resetSidebarConfig: () => void;
    renderSidebarEntries: (entries: SidebarConfigEntry[]) => Promise<void>;
    syncExpandedWidth: () => void;
    syncWithCurrentRoute: () => void;
    updateMainStateIndicator: () => void;
    updatePluginIndicator: () => void;
    updateChatIndicator: () => void;
    updateBusyIndicators: () => void;
    updateAutomationRunningIndicator: () => void;
}

const refreshSidebarContent = async (dependencies: SidebarRefreshDependencies, options: { syncRoute?: boolean } = {}): Promise<void> => {
    let entries = dependencies.getVisibleConfig();
    if (!entries.length || !entries.some((entry) => entry.type === 'page')) {
        dependencies.resetSidebarConfig();
        entries = dependencies.getVisibleConfig();
    }

    await dependencies.renderSidebarEntries(entries);
    dependencies.syncExpandedWidth();

    if (options['syncRoute']) {
        dependencies.syncWithCurrentRoute();
    }
    dependencies.updateMainStateIndicator();
    dependencies.updatePluginIndicator();
    dependencies.updateChatIndicator();
    dependencies.updateBusyIndicators();
    dependencies.updateAutomationRunningIndicator();
};

const bootstrapSidebarLifecycle = async (dependencies: SidebarLifecycleDependencies): Promise<void> => {
    dependencies.dom.cacheDom();
    const sidebar = dependencies.dom.getDomRef('sidebar');
    const menu = dependencies.dom.getMenuElement();
    if (!sidebar || !menu) {
        errorHandler.warn('Sidebar', 'DOM structure unavailable', { sidebar: !!sidebar, menu: !!menu });
        throw new Error('Sidebar DOM structure is unavailable');
    }

    dependencies.session.flushSessionDisposers();
    await dependencies.session.captureAuthSnapshot();
    dependencies.presentation.setupResponsive();
    await dependencies.presentation.refreshPluginIndicatorFromStorage();
    await dependencies.runtime.initializeModelDependentNavigation();
    dependencies.presentation.updateStateUI();

    const interactionsHost: SidebarInteractionsHost = {
        addSessionDisposer: (functionValue: SidebarDisposerCandidate) => dependencies.session.addSessionDisposer(functionValue),
        on: (target: EventTarget, eventName: string, handler: (event: Event) => void) => dependencies.session.on(target, eventName, handler),
        compactSidebar: () => dependencies.presentation.compactSidebar(),
        getDomRef: (key: string) => dependencies.dom.getDomRef(key),
        getMenuElement: () => dependencies.dom.getMenuElement(),
        isExpanded: () => dependencies.presentation.isExpanded(),
        navigateTo: (pageId: string) => dependencies.presentation.navigateTo(pageId)
    };

    bindSidebarToggleHandlers(interactionsHost);
    bindSidebarLogoNavigation(interactionsHost);
    await dependencies.presentation.refreshSidebar();
    bindSidebarNavigation(interactionsHost);

    dependencies.presentation.updatePluginIndicator();
    dependencies.presentation.updateAutomationRunningIndicator();
    dependencies.subscriptions.setupChatCompletionWatcher();
    dependencies.subscriptions.setupChatStreamingWatcher();
    dependencies.subscriptions.setupTaskBusyWatcher();
    dependencies.subscriptions.setupAutomationRunWatcher();
    dependencies.subscriptions.setupLanguageListener();
    dependencies.subscriptions.setupSidebarCustomizationListener();
    dependencies.subscriptions.setupFirstRunListener();
    dependencies.subscriptions.setupAuthListener();
    dependencies.subscriptions.initializeVersionSources();
    dependencies.presentation.handleResize();
    dependencies.presentation.syncWithCurrentRoute();

    getLayoutRuntimeManager().addBodyClass('sidebar-ready');
    dependencies.runtime.updateInitialized(true);
    dispatchCustomEvent(SIDEBAR_READY_EVENT, { instanceId: dependencies.runtime.getInstanceId() });
};

const teardownSidebarLifecycle = async (dependencies: SidebarLifecycleDependencies, initialized: boolean): Promise<void> => {
    if (!initialized) {
        dependencies.dom.cleanupMenu();
        return;
    }

    dependencies.runtime.updateInitialized(false);
    getLayoutRuntimeManager().removeBodyClass('sidebar-ready');
    dependencies.session.flushSessionDisposers();
    dependencies.runtime.cleanupModelDependentNavigation();
    dependencies.subscriptions.clearBusyIndicators();
    dependencies.subscriptions.destroyVersionController();
    await dependencies.runtime.cleanupResources();
    dependencies.dom.cleanupMenu();

    resetSidebarBodyState();
    dispatchCustomEvent(SIDEBAR_DESTROYED_EVENT, { instanceId: dependencies.runtime.getInstanceId() });
};

export { bootstrapSidebarLifecycle, refreshSidebarContent, teardownSidebarLifecycle };
export type { SidebarLifecycleDependencies, SidebarRefreshDependencies };
