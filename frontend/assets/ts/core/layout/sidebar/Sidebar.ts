/* SoAI - Shared layout sidebar [frontend/assets/ts/core/layout/sidebar/Sidebar.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getAuthManager } from '@core/auth/public.ts';
import { requireChatConversationAttention } from '@core/chat/streamServiceAccess.ts';
import { getComponentRegistry } from '@core/componentsupport/public.ts';
import { dom } from '@core/dom/dom.ts';
import { getLocation } from '@core/environment/public.ts';
import { LifecycleModel } from '@core/LifecycleModel.ts';
import type { Router } from '@core/routing/router/Router.ts';
import { requireRouter } from '@core/routing/router/routerRuntime.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { cloneSidebarConfigEntries, createSidebarAuxControllers, createSidebarRendererHost, createSidebarStaticConfig, type SidebarAuxControllers } from '@core/layout/sidebar/adapters.ts';
import { resolveAuthManager, resolveComponentRegistry, type AuthManagerContract, type ComponentRegistryContract, type UserInfo } from '@core/layout/sidebar/contracts.ts';
import { addSidebarDisposer, flushSidebarDisposers, type SidebarDisposerCandidate } from '@core/layout/sidebar/disposers.ts';
import { cacheSidebarDomRefs, getSidebarAutomationLink, getSidebarChatLink, getSidebarDomRef, getSidebarMenuElement, getSidebarPageLink, getSidebarPluginsLink } from '@core/layout/sidebar/domRefs.ts';
import { createSidebarDependencyBundle } from '@core/layout/sidebar/effects.ts';
import { bindSidebarRouteEvents } from '@core/layout/sidebar/events.ts';
import { AsyncQueue, normalizeRoute } from '@core/layout/sidebar/foundation.ts';
import { bootstrapSidebarLifecycle, refreshSidebarContent, teardownSidebarLifecycle, type SidebarLifecycleDependencies, type SidebarRefreshDependencies } from '@core/layout/sidebar/lifecycle.ts';
import { SidebarModelDependentNavigationGate } from '@core/layout/sidebar/modelDependentNavigation.ts';
import { setSidebarActiveByPage, syncSidebarWithCurrentRoute } from '@core/layout/sidebar/navigation.ts';
import { isSidebarStoragePluginIndicatorContract, type SidebarStoragePluginIndicatorContract } from '@core/layout/sidebar/pluginIndicator.ts';
import { resolveSidebarIconMarkup, resolveSidebarLabel, resolveSidebarStorage, updateSidebarMainStateIndicator, waitForSidebarComponent } from '@core/layout/sidebar/service.ts';
import { createInitialSidebarState, type SidebarState } from '@core/layout/sidebar/state.ts';
import { closeSidebarMobile, compactSidebarState, isSidebarExpanded, toggleSidebarState, updateSidebarStateUI } from '@core/layout/sidebar/stateUi.ts';
import { SidebarRenderer, type SidebarConfigEntry } from '@core/layout/sidebar/view.ts';

class LayoutSidebar extends LifecycleModel {
    readonly #adminOnlyItems: Set<string>;
    readonly #defaultSidebarConfig: ReadonlyArray<SidebarConfigEntry>;
    readonly #routeBlocklist: Set<string>;
    readonly #routeComponentMap: Record<string, string>;
    #sidebarConfig: SidebarConfigEntry[] = [];
    #instanceId: string | null = null;
    #state: SidebarState = createInitialSidebarState();
    #sidebarReady: boolean = false;
    #router: Router | null = null;
    #componentRegistry: ComponentRegistryContract | null = null;
    #authManager: AuthManagerContract | null = null;
    #currentUser: UserInfo | null = null;
    #domRefs: Map<string, HTMLElement | null> = new Map();
    #sessionDisposers: Set<() => void> = new Set();
    #persistentDisposers: Set<() => void> = new Set();
    #renderQueue: AsyncQueue = new AsyncQueue();
    #routeQueue: AsyncQueue = new AsyncQueue();
    #renderer: SidebarRenderer;
    #storage: SidebarStoragePluginIndicatorContract | null = null;
    #pluginIndicator: SidebarAuxControllers['pluginIndicator'];
    #chatIndicator: SidebarAuxControllers['chatIndicator'];
    #busyIndicatorRegistry: SidebarAuxControllers['busyIndicatorRegistry'];
    #automationRunningIndicator: SidebarAuxControllers['automationRunningIndicator'];
    #versionController: SidebarAuxControllers['versionController'];
    #modelDependentNavigation: SidebarModelDependentNavigationGate;
    #lifecycleDependencies: SidebarLifecycleDependencies;
    #refreshDependencies: SidebarRefreshDependencies;

    constructor() {
        super({ name: 'LayoutSidebar', type: 'component' });
        const staticConfig = createSidebarStaticConfig();
        this.#routeComponentMap = staticConfig.routeComponentMap;
        this.#routeBlocklist = staticConfig.routeBlocklist;
        this.#adminOnlyItems = staticConfig.adminOnlyItems;
        this.#defaultSidebarConfig = staticConfig.defaultSidebarConfig;

        this.#sidebarConfig = cloneSidebarConfigEntries(this.#defaultSidebarConfig);
        const rendererHost = createSidebarRendererHost({
            getMenuElement: () => getSidebarMenuElement(this.#domRefs),
            resolveLabel: (cfg: SidebarConfigEntry) => resolveSidebarLabel(cfg),
            resolveIconMarkup: async (icon) => resolveSidebarIconMarkup(icon),
            waitForComponent: (name: string | null) => waitForSidebarComponent(this.#componentRegistry, name, 5000),
            updateMainStateIndicator: () => updateSidebarMainStateIndicator(this.#componentRegistry, this.#state)
        });
        this.#renderer = new SidebarRenderer(rendererHost, dom);
        const auxControllers = createSidebarAuxControllers({
            getPluginsLink: () => getSidebarPluginsLink(this.#domRefs),
            getChatLink: () => getSidebarChatLink(this.#domRefs),
            getModelsLink: () => getSidebarPageLink(this.#domRefs, 'models'),
            getFileExplorerLink: () => getSidebarPageLink(this.#domRefs, 'fileExplorer'),
            getAutomationLink: () => getSidebarAutomationLink(this.#domRefs),
            resolveStorage: () => this.#resolveStorage(),
            getDisplayState: () => ({
                collapsed: this.#state.collapsed,
                mobile: this.#state.mobile,
                open: this.#state.open
            }),
            getDomRef: (key) => getSidebarDomRef(this.#domRefs, key)
        });
        this.#pluginIndicator = auxControllers.pluginIndicator;
        this.#chatIndicator = auxControllers.chatIndicator;
        this.#busyIndicatorRegistry = auxControllers.busyIndicatorRegistry;
        this.#automationRunningIndicator = auxControllers.automationRunningIndicator;
        this.#versionController = auxControllers.versionController;
        this.#modelDependentNavigation = new SidebarModelDependentNavigationGate({
            refreshSidebar: (options?: { syncRoute?: boolean }) => refreshSidebarContent(this.#refreshDependencies, options)
        });
        const dependencies = createSidebarDependencyBundle({
            stateOwner: {
                domRefs: this.#domRefs,
                state: this.#state,
                routeComponentMap: this.#routeComponentMap,
                adminOnlyItems: this.#adminOnlyItems,
                getCurrentUser: () => this.#currentUser,
                setCurrentUser: (user: UserInfo | null) => (this.#currentUser = user),
                updateInitialized: (value: boolean) => (this.#sidebarReady = value),
                getInstanceId: () => this.#instanceId
            },
            indicators: {
                pluginIndicator: this.#pluginIndicator,
                chatIndicator: this.#chatIndicator,
                busyIndicatorRegistry: this.#busyIndicatorRegistry,
                automationRunningIndicator: this.#automationRunningIndicator,
                versionController: this.#versionController
            },
            rendering: {
                getSidebarConfig: () => this.#sidebarConfig,
                setSidebarConfig: (entries) => (this.#sidebarConfig = entries),
                cloneDefaultConfig: () => cloneSidebarConfigEntries(this.#defaultSidebarConfig),
                renderSidebarEntries: (entries: SidebarConfigEntry[]) => this.#renderQueue.run(() => this.#renderer.render(entries))
            },
            services: {
                getAuthManager: () => this.#authManager,
                getRouter: () => this.#router,
                getComponentRegistry: () => this.#componentRegistry,
                addSessionDisposer: (functionValue: SidebarDisposerCandidate) => addSidebarDisposer(this.#sessionDisposers, functionValue, 'session'),
                flushSessionDisposers: () => flushSidebarDisposers(this.#sessionDisposers, 'session'),
                on: (target: EventTarget | Element, eventName: string, handler: (event: Event) => void) => this.lifecycleResources.addEventListener(target, eventName, handler),
                refreshSidebar: (options?: { syncRoute?: boolean }) => refreshSidebarContent(this.#refreshDependencies, options),
                filterModelDependentNavigation: (entries) => this.#modelDependentNavigation.filterEntries(entries),
                closeMobile: async () => {
                    if (closeSidebarMobile(this.#state)) this.#updateStateUi();
                }
            },
            lifecycle: {
                initializeModelDependentNavigation: () => this.#modelDependentNavigation.initialize(),
                cleanupModelDependentNavigation: () => this.#modelDependentNavigation.dispose(),
                cleanupResources: () => super.cleanupResources()
            }
        });
        this.#refreshDependencies = dependencies.refreshDependencies;
        this.#lifecycleDependencies = dependencies.lifecycleDependencies;
    }

    #resolveStorage(): Promise<SidebarStoragePluginIndicatorContract | null> {
        const resolved = resolveSidebarStorage(this.#storage);
        if (resolved && isSidebarStoragePluginIndicatorContract(resolved)) this.#storage = resolved;
        return Promise.resolve(this.#storage);
    }

    #updateStateUi(): void {
        updateSidebarStateUI(this.#state, this.#domRefs, this.#versionController, () => updateSidebarMainStateIndicator(this.#componentRegistry, this.#state));
    }

    async initialize(): Promise<void> {
        if (this.isInitialized || this.isDestroyed) {
            if (!this.isDestroyed) {
                await this.destroy();
            }
            this.resetLifecycleState();
        }
        await this.initializeLifecycle();
    }

    override async onInitialize(): Promise<void> {
        if (!this.#instanceId) this.#instanceId = generateSecureId({ prefix: 'sidebar', format: 'hex' });

        await this.ensureDeclaredResources();
        this.#router = requireRouter();
        this.#componentRegistry = resolveComponentRegistry(getComponentRegistry());
        this.#authManager = resolveAuthManager(getAuthManager());

        cacheSidebarDomRefs(this.#domRefs);
        flushSidebarDisposers(this.#persistentDisposers, 'persistent');
        const enqueueRouteChange = bindSidebarRouteEvents({
            addPersistentDisposer: (functionValue) => addSidebarDisposer(this.#persistentDisposers, functionValue, 'persistent'),
            routeBlocklist: this.#routeBlocklist,
            getMenuElement: () => getSidebarMenuElement(this.#domRefs),
            getCurrentRoute: () => this.#router?.getCurrentRoute?.() || null,
            getRouteFromHash: () => this.#router?.getRouteFromHash?.() || null,
            isInitialized: () => this.#sidebarReady,
            hasSidebarReadyClass: () => document.body.classList.contains('sidebar-ready'),
            bootstrapSidebar: () => bootstrapSidebarLifecycle(this.#lifecycleDependencies),
            teardownSidebar: () => teardownSidebarLifecycle(this.#lifecycleDependencies, this.#sidebarReady),
            syncWithCurrentRoute: () => syncSidebarWithCurrentRoute(this.#router, getSidebarMenuElement(this.#domRefs), this.#routeComponentMap),
            updateMainStateIndicator: () => updateSidebarMainStateIndicator(this.#componentRegistry, this.#state),
            markChatTerminalIndicatorsSeen: () => requireChatConversationAttention().markCurrentSnapshotSeen(),
            runRouteTask: (task: () => Promise<void>) => this.#routeQueue.run(task)
        });

        const locationRef = getLocation();
        const route = normalizeRoute(this.#router?.getCurrentRoute()) || normalizeRoute(this.#router?.getRouteFromHash()) || normalizeRoute(locationRef.hash?.slice(1)) || null;
        await enqueueRouteChange(route, { allowActiveSync: true });
    }

    override async onDestroy(): Promise<void> {
        await teardownSidebarLifecycle(this.#lifecycleDependencies, this.#sidebarReady);
        flushSidebarDisposers(this.#persistentDisposers, 'persistent');
        this.#sidebarConfig = cloneSidebarConfigEntries(this.#defaultSidebarConfig);
        this.#state = createInitialSidebarState();
        this.#router = null;
        this.#componentRegistry = null;
        this.#authManager = null;
        this.#currentUser = null;
        this.#domRefs.clear();
        this.#storage = null;
        this.#pluginIndicator.setVisible(false);
        this.#chatIndicator.setVisible(false);
        this.#busyIndicatorRegistry.clear();
        this.#automationRunningIndicator.setVisible(false);
        this.#versionController.destroy();
        await super.cleanupResources();
    }

    isExpanded(): boolean {
        return isSidebarExpanded(this.#state);
    }

    compactSidebar(): void {
        if (!compactSidebarState(this.#state)) {
            return;
        }
        this.#updateStateUi();
    }

    async toggle(): Promise<void> {
        toggleSidebarState(this.#state);
        this.#updateStateUi();
    }

    setActiveByPage(page: string): void {
        setSidebarActiveByPage(getSidebarMenuElement(this.#domRefs), page);
    }
}

export { LayoutSidebar };
