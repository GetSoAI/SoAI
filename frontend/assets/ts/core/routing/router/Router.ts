/* SoAI - Shared routing router [frontend/assets/ts/core/routing/router/Router.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getHistory, getLocation, getWindow } from '@core/environment/public.ts';
import type { NavigationMiddlewareController, NavigationResultType } from '@core/navigationMiddleware.ts';
import type { NotificationApi, PageContext } from '@core/pagecontext/public.ts';
import { getRouteDefinitions, getSidebarComponentTargets } from '@core/routeregistry/service.ts';
import type { SidebarComponentTargets } from '@core/routeregistry/contracts.ts';
import { RouterComponentLoader } from '@core/routing/router/componentLoader.ts';
import { resolveRouteTitle } from '@core/routing/router/navigation.ts';
import { normalizeNavigationRequest } from '@core/routing/router/navigationRequest.ts';
import { assertRouterDependencies } from '@core/routing/router/contracts.ts';
import { buildQueryRoute, getQueryParametersFromHash, registerRouterInitializationEvents } from '@core/routing/router/events.ts';
import { ensurePageHost, getRouteFromHash, parseRoutePath, registerRouteDefinitions, resolveRouteDetails } from '@core/routing/router/actions.ts';
import { acquireNavigationConnectionHold, releaseNavigationConnectionHold } from '@core/routing/router/routerConnectionHold.ts';
import type { PageOutletService, ResourceTrackerInstance, RouterDependencies } from '@core/routing/router/routerDependencies.ts';
import { createBeforeNavigateMiddleware, useRouterNavigationMiddleware, type RouterMiddleware } from '@core/routing/router/guards.ts';
import { isSidebarServiceContract, renderRouterError, resolveContainerTarget, resolveSidebarService } from '@core/routing/router/routerInternals.ts';
import { createRouterLifecycleDependencies, executeNavigationRequest } from '@core/routing/router/service.ts';
import { createRouterComposition, reloadHandler } from '@core/routing/router/routerComposition.ts';
import type { NavigationContext, NavigationOptions, NavigationRequest, NavigationTarget, RouteDefinition, RouteEntry, RouteParameters } from '@core/routing/router/types.ts';
import { isFunction, isHTMLElement } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { claimErrorReporting } from '@core/errors/reportingOwnership.ts';
import { notifyHandledOperationError } from '@core/operationErrorNotifier.ts';
import type { PageHostInstance } from '@core/pageoutlet/types.ts';
import { isAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';

class Router {
    #componentLoader: RouterComponentLoader;
    #getSidebarService: RouterDependencies['getSidebarService'];
    #lifecycleDependencies: ReturnType<typeof createRouterLifecycleDependencies>;
    #sidebarTargets: SidebarComponentTargets;
    dom: RouterDependencies['dom'];
    storage: RouterDependencies['storage'];
    auth: RouterDependencies['auth'];
    api: RouterDependencies['api'];
    streamManager: RouterDependencies['streamManager'];
    stateManager: RouterDependencies['state'];
    cleanupManager: RouterDependencies['cleanupManager'];
    sectionTracker: { cleanup: () => void; initialize: () => void };
    errorHandler: RouterDependencies['errorHandler'];
    pageContext: PageContext;
    notifications: NotificationApi;
    routes: Map<string, RouteEntry> = new Map();
    dynamicRoutes: RouteEntry[] = [];
    currentRoute: string | null = null;
    contentContainer: HTMLElement | null = null;
    pageHost: { getCurrent: PageHostInstance['getCurrent'] } | null = null;
    pageOutlet: PageOutletService;
    initialized = false;
    resources: ResourceTrackerInstance;
    routerBoundary: InstanceType<RouterDependencies['ErrorBoundary']>;
    #activeNavigation: AbortController | null = null;
    navigationMiddleware: NavigationMiddlewareController;
    constructor(dependencies: RouterDependencies) {
        assertRouterDependencies(dependencies);
        const composition = createRouterComposition(this, dependencies);
        this.errorHandler = composition.errorHandler;
        this.dom = composition.dom;
        this.storage = composition.storage;
        this.auth = composition.auth;
        this.pageContext = composition.pageContext;
        this.notifications = composition.notifications;
        this.api = composition.api;
        this.streamManager = composition.streamManager;
        this.stateManager = composition.stateManager;
        this.cleanupManager = composition.cleanupManager;
        this.sectionTracker = composition.sectionTracker;
        this.pageOutlet = composition.pageOutlet;
        this.resources = composition.resources;
        this.routerBoundary = composition.routerBoundary;
        this.navigationMiddleware = composition.navigationMiddleware;
        this.#getSidebarService = composition.getSidebarService;
        this.#componentLoader = composition.componentLoader;
        this.#lifecycleDependencies = composition.lifecycleDependencies;
        this.#sidebarTargets = getSidebarComponentTargets();
    }
    getUI(selector: string, context: Element | Document | null = null): Element | null {
        return this.dom.resolve(selector, context);
    }
    queryUI(selector: string, context: Element | Document | null = null): Element[] {
        return this.dom.resolveAll(selector, context);
    }
    initialize(contentContainerId: string | HTMLElement = 'main-content', routeDefinitions: RouteDefinition[] = getRouteDefinitions()): void {
        const targetContainer = resolveContainerTarget((selector: string, context: Element | Document | null = null) => this.dom.resolve(selector, context), contentContainerId);
        if (!targetContainer) {
            throw new Error('Router requires a valid content container element');
        }
        if (!this.initialized) {
            this.initialized = true;
            this.setContentContainer(targetContainer);
            this.registerRoutes(routeDefinitions);
            this.#componentLoader.initializeNavigationPrefetch();
            registerRouterInitializationEvents({
                resources: this.resources,
                getWindow,
                getRouteFromHash: () => this.getRouteFromHash(),
                parseRoute: (target: string) => this.parseRoute(target),
                navigate: async (target: string, options: NavigationOptions) => this.navigate(target, options),
                errorHandler: this.errorHandler,
                renderCriticalError: (message: string) => renderRouterError(this.dom, this.contentContainer, 'critical', message, reloadHandler),
                isInitialized: () => this.initialized,
                getCurrentRoute: () => this.currentRoute
            });
            return;
        }
        this.setContentContainer(targetContainer);
    }
    setContentContainer(containerTarget: string | HTMLElement | null | undefined): void {
        const resolved = resolveContainerTarget((selector: string, context?: Element | Document | null) => this.dom.resolve(selector, context), containerTarget);
        if (!isHTMLElement(resolved)) {
            throw new Error('Router requires an HTMLElement container');
        }
        this.pageOutlet.setContainer(resolved);
        this.contentContainer = this.pageOutlet.getContainer();
        this.dom.setStyle(this.contentContainer, 'opacity', null);
        this.pageHost = ensurePageHost(this.pageOutlet);
    }
    ensureInitialized(): void {
        if (!this.initialized || !this.contentContainer) {
            this.initialize();
        }
        if (!this.contentContainer) {
            throw new Error('Router requires a content container');
        }
    }
    registerRoutes(routeDefinitions: RouteDefinition[] = getRouteDefinitions()): void {
        registerRouteDefinitions(routeDefinitions, this.routes, this.dynamicRoutes);
    }
    getRouteFromHash(): string | null {
        return getRouteFromHash(getLocation().hash);
    }
    parseRoute(routePath: string): { route: RouteEntry; parameters: RouteParameters } | null {
        return parseRoutePath(routePath, this.routes, this.dynamicRoutes);
    }
    async navigate(target: string | NavigationTarget, options: NavigationOptions = {}): Promise<void> {
        return this.routerBoundary.execute(async () => {
            const request = normalizeNavigationRequest(target, options);
            this.#activeNavigation?.abort('navigation-superseded');
            const navigation = new AbortController();
            this.#activeNavigation = navigation;
            try {
                await raceWithAbortSignal(this.pageOutlet.waitForCommit(), navigation.signal);
                await this.#navigateInternal(request, navigation.signal);
            } catch (error) {
                if (!isAbortError(error) || !navigation.signal.aborted) throw error;
            } finally {
                if (this.#activeNavigation === navigation) {
                    this.#activeNavigation = null;
                    this.pageOutlet.cancelActive('navigation-settled');
                }
            }
        }, 'navigate');
    }
    useNavigationMiddleware(middleware: RouterMiddleware, options: { priority: number }): () => void {
        return useRouterNavigationMiddleware(this.navigationMiddleware, middleware, options);
    }
    async #navigateInternal(request: NavigationRequest, signal: AbortSignal): Promise<void> {
        await executeNavigationRequest({
            router: { parseRoute: (path: string) => this.parseRoute(path) },
            state: {
                currentRoute: this.currentRoute,
                setCurrentRoute: (route: string) => {
                    this.currentRoute = route;
                },
                setLastNavigationDetail: () => {}
            },
            request,
            parseRoute: (path: string) => this.parseRoute(path),
            resolveRouteDetails: (path: string, route: RouteDefinition | null, parameters: RouteParameters | null) =>
                resolveRouteDetails({
                    ensureInitialized: () => this.ensureInitialized(),
                    path,
                    route,
                    parameters,
                    parseRoute: (targetPath: string) => this.parseRoute(targetPath)
                }),
            validateNavigation: (route: RouteDefinition) => {
                if (!route.component) {
                    throw new Error('Route missing component');
                }
            },
            runNavigationMiddleware: async (context: NavigationContext) => this.navigationMiddleware.run(context),
            preloadDependencies: async (route: RouteDefinition) => this.#componentLoader.preloadDependencies(route, signal),
            pageOutlet: this.pageOutlet,
            redirect: async (target: string, options: NavigationOptions) => {
                await this.#navigateInternal(normalizeNavigationRequest(target, { ...options, force: true }), signal);
            },
            lifecycle: this.#lifecycleDependencies,
            sectionTracker: this.sectionTracker,
            loadPageComponent: async (componentName: string, parameters: RouteParameters, renderOptions: { beforePrepare: () => Promise<void>; beforeCommit: () => Promise<void>; commitNavigation: () => void; signal: AbortSignal }): Promise<boolean> => {
                const rendered = await this.pageOutlet.render({ component: componentName, parameters, ...renderOptions });
                return rendered !== null;
            },
            sidebarTargets: this.#sidebarTargets,
            resolveSidebarService: () => resolveSidebarService(this.#getSidebarService, isSidebarServiceContract),
            historyApi: getHistory(),
            resolveRouteTitle,
            connectionHold: {
                acquire: acquireNavigationConnectionHold,
                release: releaseNavigationConnectionHold
            },
            signal
        });
    }
    beforeNavigate(callback: (route: RouteDefinition, parameters: RouteParameters, context: NavigationContext) => Promise<NavigationResultType | boolean | void | null>): () => void {
        const middleware = createBeforeNavigateMiddleware(callback);
        return this.useNavigationMiddleware(middleware, { priority: 10 });
    }
    getCurrentRoute(): string | null {
        return this.currentRoute;
    }
    replaceCurrentRoute(target: string | NavigationTarget): void {
        this.ensureInitialized();
        const currentRoute = this.currentRoute;
        if (!currentRoute) {
            throw new Error('Router cannot replace the current route before a route is active');
        }
        const currentRouteInfo = this.parseRoute(currentRoute);
        if (!currentRouteInfo) {
            throw new Error(`Router cannot parse current route: ${currentRoute}`);
        }
        const request = normalizeNavigationRequest(target);
        const resolvedTarget = resolveRouteDetails({
            ensureInitialized: () => this.ensureInitialized(),
            path: request.path,
            route: request.route,
            parameters: request.parameters,
            parseRoute: (routePath: string) => this.parseRoute(routePath)
        });
        if (currentRouteInfo.route.component !== resolvedTarget.route.component) {
            throw new Error(`Router cannot replace current route across components: ${currentRouteInfo.route.component} -> ${resolvedTarget.route.component}`);
        }
        const title = resolveRouteTitle(resolvedTarget.route);
        getHistory().replaceState({ route: resolvedTarget.path }, title, `#${resolvedTarget.path}`);
        this.currentRoute = resolvedTarget.path;
    }
    getRouteParameters(): RouteParameters {
        if (!this.currentRoute) {
            throw new Error('Router does not have an active route');
        }
        const parsed = this.parseRoute(this.currentRoute);
        if (!parsed) {
            throw new Error(`Router cannot parse current route: ${this.currentRoute}`);
        }
        return parsed.parameters;
    }
    async reload(): Promise<void> {
        if (this.currentRoute) {
            await this.navigate(this.currentRoute, { pushState: false, force: true });
        }
    }
    async destroyCurrentPage(): Promise<void> {
        await this.pageOutlet.destroyCurrent({ force: true });
        await this.cleanupManager.cleanupAll();
    }

    async destroy(): Promise<void> {
        this.#activeNavigation?.abort('router-destroyed');
        this.#activeNavigation = null;
        this.resources.cleanup();
        const pageOutlet = this.pageOutlet;
        if (isFunction(pageOutlet.destroy)) {
            await pageOutlet.destroy();
        } else {
            await pageOutlet.destroyCurrent({ force: true });
        }
        await this.cleanupManager.cleanupAll();
        this.sectionTracker.cleanup();
        this.currentRoute = null;
        this.pageHost = null;
        this.contentContainer = null;
        this.initialized = false;
    }
    getPageOutlet(): PageOutletService {
        return this.pageOutlet;
    }
    navigateWithQuery(path: string, queryParameters: Record<string, string> = {}, options: NavigationOptions = {}): void {
        this.navigate(buildQueryRoute(path, queryParameters), options).catch((error) => {
            const runtimeError = ensureError(error);
            if (!claimErrorReporting(runtimeError)) {
                return;
            }
            notifyHandledOperationError(runtimeError);
            this.errorHandler.error('Router', 'navigateWithQuery failed', runtimeError);
        });
    }
    getQueryParameters(): RouteParameters {
        return getQueryParametersFromHash(getLocation().hash);
    }
}

export { Router };
