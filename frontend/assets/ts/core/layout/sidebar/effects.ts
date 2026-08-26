/* SoAI - Shared layout sidebar effects [frontend/assets/ts/core/layout/sidebar/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { Router } from '@core/routing/router/Router.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import type { SidebarBusyIndicatorRegistry } from '@core/layout/sidebar/busyIndicatorRegistry.ts';
import type { AuthManagerContract, ComponentRegistryContract, UserInfo } from '@core/layout/sidebar/contracts.ts';
import { cacheSidebarDomRefs, clearSidebarMenu, getSidebarDomRef, getSidebarMenuElement } from '@core/layout/sidebar/domRefs.ts';
import type { SidebarDisposerCandidate } from '@core/layout/sidebar/disposers.ts';
import type { SidebarLifecycleDependencies, SidebarRefreshDependencies } from '@core/layout/sidebar/lifecycle.ts';
import { navigateSidebarTo, syncSidebarWithCurrentRoute, updateSidebarAdminMenuItems } from '@core/layout/sidebar/navigation.ts';
import type { SidebarLinkIndicatorController } from '@core/layout/sidebar/linkIndicator.ts';
import { subscribeChatCompletionWatcher } from '@core/layout/sidebar/chatCompletionWatcher.ts';
import { subscribeChatStreamingWatcher } from '@core/layout/sidebar/chatStreamingWatcher.ts';
import { subscribeAutomationRunWatcher } from '@core/layout/sidebar/automationRunWatcher.ts';
import type { SidebarPluginIndicatorController } from '@core/layout/sidebar/pluginIndicator.ts';
import { captureSidebarAuthSnapshot, getVisibleSidebarConfig, loadSidebarGrantedActions, syncSidebarExpandedWidth, updateSidebarMainStateIndicator } from '@core/layout/sidebar/service.ts';
import { setupSidebarAuthListener, setupSidebarCustomizationListener, setupSidebarFirstRunListener, setupSidebarLanguageListener, type SidebarSessionListenerDependencies } from '@core/layout/sidebar/sessionListeners.ts';
import type { SidebarState } from '@core/layout/sidebar/state.ts';
import { compactSidebarState, handleSidebarResize, isSidebarExpanded, updateSidebarStateUI } from '@core/layout/sidebar/stateUi.ts';
import { subscribeSidebarTaskBusyWatcher } from '@core/layout/sidebar/taskBusyWatcher.ts';
import type { SidebarVersionController } from '@core/layout/sidebar/version.ts';
import type { SidebarConfigEntry } from '@core/layout/sidebar/view.ts';

interface SidebarDependencyBundle {
    refreshDependencies: SidebarRefreshDependencies;
    lifecycleDependencies: SidebarLifecycleDependencies;
}

interface SidebarStateOwner {
    domRefs: Map<string, HTMLElement | null>;
    state: SidebarState;
    routeComponentMap: Record<string, string>;
    adminOnlyItems: Set<string>;
    getCurrentUser: () => UserInfo | null;
    setCurrentUser: (user: UserInfo | null) => void;
    updateInitialized: (value: boolean) => void;
    getInstanceId: () => string | null;
}

interface SidebarIndicatorOwners {
    pluginIndicator: SidebarPluginIndicatorController;
    chatIndicator: SidebarLinkIndicatorController;
    busyIndicatorRegistry: SidebarBusyIndicatorRegistry;
    automationRunningIndicator: SidebarLinkIndicatorController;
    versionController: SidebarVersionController;
}

interface SidebarRenderingOwner {
    getSidebarConfig: () => SidebarConfigEntry[];
    setSidebarConfig: (entries: SidebarConfigEntry[]) => void;
    cloneDefaultConfig: () => SidebarConfigEntry[];
    renderSidebarEntries: (entries: SidebarConfigEntry[]) => Promise<void>;
}

interface SidebarServiceAccess {
    getAuthManager: () => AuthManagerContract | null;
    getRouter: () => Router | null;
    getComponentRegistry: () => ComponentRegistryContract | null;
    addSessionDisposer: (functionValue: SidebarDisposerCandidate) => () => void;
    flushSessionDisposers: () => void;
    on: (target: EventTarget | Element, eventName: string, handler: (event: Event) => void) => () => void;
    refreshSidebar: (options?: { syncRoute?: boolean }) => Promise<void>;
    filterModelDependentNavigation: (entries: SidebarConfigEntry[]) => SidebarConfigEntry[];
    closeMobile: () => Promise<void>;
}

interface SidebarLifecycleOwner {
    initializeModelDependentNavigation: () => Promise<void>;
    cleanupModelDependentNavigation: () => void;
    cleanupResources: () => Promise<void>;
}

interface SidebarDependencyContext {
    stateOwner: SidebarStateOwner;
    indicators: SidebarIndicatorOwners;
    rendering: SidebarRenderingOwner;
    services: SidebarServiceAccess;
    lifecycle: SidebarLifecycleOwner;
}

const createSidebarDependencyBundle = (context: SidebarDependencyContext): SidebarDependencyBundle => {
    let grantedActionsLoadSequence = 0;

    const refreshGrantedActionsForUser = async (user: UserInfo | null): Promise<void> => {
        const sequence = grantedActionsLoadSequence + 1;
        grantedActionsLoadSequence = sequence;
        const grantedActions = await loadSidebarGrantedActions(user);
        if (sequence === grantedActionsLoadSequence) {
            context.stateOwner.state.grantedActions = grantedActions;
        }
    };

    const updateExpandedWidth = (): void => {
        syncSidebarExpandedWidth(getSidebarDomRef(context.stateOwner.domRefs, 'sidebar'));
    };

    const updateStateUi = (): void => {
        updateSidebarStateUI(context.stateOwner.state, context.stateOwner.domRefs, context.indicators.versionController, () => updateSidebarMainStateIndicator(context.services.getComponentRegistry(), context.stateOwner.state));
        updateExpandedWidth();
    };

    const sessionListenerDependencies: SidebarSessionListenerDependencies = {
        on: (target: EventTarget | Element, event: string, handler: EventListener) => context.services.on(target, event, handler),
        addSessionDisposer: (functionValue: SidebarDisposerCandidate) => context.services.addSessionDisposer(functionValue),
        refreshSidebar: (options?: { syncRoute?: boolean }) => context.services.refreshSidebar(options),
        refreshPluginIndicatorFromStorage: () => context.indicators.pluginIndicator.refreshFromStorage(),
        setCurrentUser: (user: UserInfo | null) => {
            context.stateOwner.setCurrentUser(user);
        },
        refreshGrantedActions: (user: UserInfo | null) => refreshGrantedActionsForUser(user),
        getAuthManager: () => context.services.getAuthManager()
    };

    const refreshDependencies: SidebarRefreshDependencies = {
        getVisibleConfig: () => context.services.filterModelDependentNavigation(getVisibleSidebarConfig(context.rendering.getSidebarConfig(), context.stateOwner.adminOnlyItems, context.stateOwner.getCurrentUser(), context.stateOwner.state.grantedActions)),
        resetSidebarConfig: () => {
            context.rendering.setSidebarConfig(context.rendering.cloneDefaultConfig());
        },
        renderSidebarEntries: (entries: SidebarConfigEntry[]) => context.rendering.renderSidebarEntries(entries),
        updateMenuItems: () => updateSidebarAdminMenuItems(getSidebarMenuElement(context.stateOwner.domRefs), context.stateOwner.adminOnlyItems, context.stateOwner.getCurrentUser()),
        syncExpandedWidth: () => updateExpandedWidth(),
        syncWithCurrentRoute: () => syncSidebarWithCurrentRoute(context.services.getRouter(), getSidebarMenuElement(context.stateOwner.domRefs), context.stateOwner.routeComponentMap),
        updateMainStateIndicator: () => updateSidebarMainStateIndicator(context.services.getComponentRegistry(), context.stateOwner.state),
        updatePluginIndicator: () => context.indicators.pluginIndicator.updateIndicator(),
        updateChatIndicator: () => context.indicators.chatIndicator.updateIndicator(),
        updateBusyIndicators: () => context.indicators.busyIndicatorRegistry.updateIndicators(),
        updateAutomationRunningIndicator: () => context.indicators.automationRunningIndicator.updateIndicator()
    };

    const lifecycleDependencies: SidebarLifecycleDependencies = {
        dom: {
            cacheDom: () => cacheSidebarDomRefs(context.stateOwner.domRefs),
            getDomRef: (key: string) => getSidebarDomRef(context.stateOwner.domRefs, key),
            getMenuElement: () => getSidebarMenuElement(context.stateOwner.domRefs),
            cleanupMenu: () => clearSidebarMenu(context.stateOwner.domRefs)
        },
        session: {
            flushSessionDisposers: () => context.services.flushSessionDisposers(),
            captureAuthSnapshot: async () => {
                const currentUser = captureSidebarAuthSnapshot(context.services.getAuthManager()?.user);
                context.stateOwner.setCurrentUser(currentUser);
                await refreshGrantedActionsForUser(currentUser);
            },
            on: (target: EventTarget | Element, eventName: string, handler: (event: Event) => void) => context.services.on(target, eventName, handler),
            addSessionDisposer: (functionValue: SidebarDisposerCandidate) => context.services.addSessionDisposer(functionValue)
        },
        presentation: {
            setupResponsive: () => {
                const updateResponsiveState = (): void => {
                    handleSidebarResize(context.stateOwner.state);
                    updateStateUi();
                };
                context.services.addSessionDisposer(context.services.on(window, 'resize', updateResponsiveState));
                context.services.addSessionDisposer(context.services.on(window, INTERFACE_SCALE_CHANGED_EVENT, updateResponsiveState));
            },
            refreshPluginIndicatorFromStorage: () => context.indicators.pluginIndicator.refreshFromStorage(),
            updateStateUI: () => updateStateUi(),
            compactSidebar: () => {
                if (compactSidebarState(context.stateOwner.state)) updateStateUi();
            },
            isExpanded: () => isSidebarExpanded(context.stateOwner.state),
            navigateTo: (pageId: string) => navigateSidebarTo(context.services.getRouter(), pageId, getSidebarMenuElement(context.stateOwner.domRefs), context.stateOwner.state.mobile, () => context.services.closeMobile()),
            refreshSidebar: (options?: { syncRoute?: boolean }) => context.services.refreshSidebar(options),
            updatePluginIndicator: () => context.indicators.pluginIndicator.updateIndicator(),
            updateAutomationRunningIndicator: () => context.indicators.automationRunningIndicator.updateIndicator(),
            handleResize: () => {
                handleSidebarResize(context.stateOwner.state);
                updateStateUi();
            },
            syncWithCurrentRoute: () => syncSidebarWithCurrentRoute(context.services.getRouter(), getSidebarMenuElement(context.stateOwner.domRefs), context.stateOwner.routeComponentMap)
        },
        subscriptions: {
            updateBusyIndicators: () => context.indicators.busyIndicatorRegistry.updateIndicators(),
            setupChatCompletionWatcher: () => context.services.addSessionDisposer(subscribeChatCompletionWatcher(context.indicators.chatIndicator)),
            setupChatStreamingWatcher: () => context.services.addSessionDisposer(subscribeChatStreamingWatcher(context.indicators.busyIndicatorRegistry)),
            setupTaskBusyWatcher: () => context.services.addSessionDisposer(subscribeSidebarTaskBusyWatcher(context.indicators.busyIndicatorRegistry)),
            setupAutomationRunWatcher: () => context.services.addSessionDisposer(subscribeAutomationRunWatcher(context.indicators.automationRunningIndicator)),
            setupLanguageListener: () => setupSidebarLanguageListener(sessionListenerDependencies),
            setupSidebarCustomizationListener: () => setupSidebarCustomizationListener(sessionListenerDependencies),
            setupFirstRunListener: () => setupSidebarFirstRunListener(sessionListenerDependencies),
            setupAuthListener: () => setupSidebarAuthListener(sessionListenerDependencies),
            initializeVersionSources: () => terminateHandledPromise(context.indicators.versionController.initializeSources()),
            clearBusyIndicators: () => context.indicators.busyIndicatorRegistry.clear(),
            destroyVersionController: () => context.indicators.versionController.destroy()
        },
        runtime: {
            initializeModelDependentNavigation: () => context.lifecycle.initializeModelDependentNavigation(),
            cleanupModelDependentNavigation: () => context.lifecycle.cleanupModelDependentNavigation(),
            updateInitialized: (value: boolean) => context.stateOwner.updateInitialized(value),
            getInstanceId: () => context.stateOwner.getInstanceId(),
            cleanupResources: () => context.lifecycle.cleanupResources()
        }
    };

    return { refreshDependencies, lifecycleDependencies };
};

export { createSidebarDependencyBundle };
export type { SidebarDependencyBundle, SidebarDependencyContext };
