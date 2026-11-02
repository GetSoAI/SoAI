/* SoAI - Shared routing router [frontend/assets/ts/core/routing/router/Router.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getHistory, getLocation, getWindow } from '@core/environment/public.ts';
import type { NavigationMiddlewareController } from '@core/navigationMiddleware.ts';
import type { NavigationResultType, NavigationContext, NavigationOptions, NavigationTarget, RouteDefinition, RouteEntry, RouteParameters } from '@core/routing/router/types.ts';
import type { NotificationApi, PageContext } from '@core/pagecontext/public.ts';
import { getRouteDefinitions, getSidebarComponentTargets } from '@core/routeregistry/service.ts';
import type { SidebarComponentTargets } from '@core/routeregistry/contracts.ts';
import { RouterComponentLoader } from '@core/routing/router/componentLoader.ts';
import { resolveDefaultAuthenticatedRoute } from '@core/routing/router/authRouteTarget.ts';
import { normalizeNavigationRequest } from '@core/routing/router/navigationRequest.ts';
import { assertRouterDependencies } from '@core/routing/router/contracts.ts';
import { registerRouterInitializationEvents, reportNavigationEventFailure, type BrowserNavigationTarget, type RouterBrowserNavigation } from '@core/routing/router/events.ts';
import { buildQueryRoute } from '@core/routing/router/queryParameters.ts';
import { ensurePageHost, getRouteFromHash, parseRoutePath, registerRouteDefinitions, resolveRouteDetails } from '@core/routing/router/actions.ts';
import type { ResourceTrackerInstance, RouterDependencies } from '@core/routing/router/routerDependencies.ts';
import type { PageOutletService, PageHostInstance } from '@core/pageoutlet/types.ts';
import { createBeforeNavigateMiddleware, useRouterNavigationMiddleware, type RouterMiddleware } from '@core/routing/router/guards.ts';
import { renderRouterError, resolveContainerTarget, isSidebarServiceContract, resolveSidebarService } from '@core/routing/router/routerInternals.ts';
import { createRouterLifecycleDependencies } from '@core/routing/router/service.ts';
import { createRouterComposition, reloadHandler } from '@core/routing/router/routerComposition.ts';

import { isFunction, isHTMLElement } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { claimErrorReporting } from '@core/errors/reportingOwnership.ts';
import { notifyHandledOperationError } from '@core/operationErrorNotifier.ts';

import { executeRoutePaneNavigation } from '@core/routing/router/routeExecution.ts';
import { RoutePane } from '@core/routing/router/RoutePane.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { getLanguageService } from '@core/languageservice/service.ts';
import { resolveRouteTitle } from '@core/routing/router/navigation.ts';
import { runCleanupStepCollectingFailure } from '@core/lifecycle/cleanup.ts';
import { projectFocusedPane, updateSidebarActiveState } from '@core/routing/router/pageOutlet.ts';

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
    contentContainer: HTMLElement | null = null;
    readonly #createPaneResources: ReturnType<typeof createRouterComposition>['createPaneResources'];
    initialized = false;
    resources: ResourceTrackerInstance;
    routerBoundary: InstanceType<RouterDependencies['ErrorBoundary']>;
    readonly #primaryPane: RoutePane;
    readonly pagePanes: RouterDependencies['pagePanes'];
    #browserNavigationSuspended = false;
    readonly #browserNavigation: RouterBrowserNavigation;
    #focusedProjection: { paneId: string; route: string; generation: symbol | null } | null = null;
    navigationMiddleware: NavigationMiddlewareController;
    constructor(dependencies: RouterDependencies) {
        assertRouterDependencies(dependencies);
        this.pagePanes = dependencies.pagePanes;
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
        this.#createPaneResources = composition.createPaneResources;
        this.resources = composition.resources;
        this.routerBoundary = composition.routerBoundary;
        this.navigationMiddleware = composition.navigationMiddleware;
        this.#browserNavigation = composition.browserNavigation;
        this.#getSidebarService = composition.getSidebarService;
        this.#componentLoader = composition.componentLoader;
        this.#lifecycleDependencies = composition.lifecycleDependencies;
        this.#sidebarTargets = getSidebarComponentTargets();
        this.#primaryPane = this.#createPane();
        this.pagePanes.configureAdmission({ createPane: (id) => this.#createPane(id), parseRoute: (path) => this.parseRoute(path), readAuthEpoch: () => this.auth.authEpoch, modalPresenter: dependencies.modalPresenter });
    }
    #createPane(id = generateSecureId('pane')): RoutePane {
        return new RoutePane({
            id,
            createResources: (pane) =>
                this.#createPaneResources({
                    getLanguage: () => getLanguageService().getLanguage(),
                    getCurrentRoute: () => pane.currentRoute,
                    getHashRoute: () => null,
                    getNavigationCompletion: () => pane.getLatestNavigationCompletion(),
                    canRefresh: () => this.initialized && !this.isBrowserNavigationSuspended() && this.contentContainer?.inert !== true && this.pagePanes.getPanes().includes(pane) && this.pagePanes.getPaneSlot(pane).state === 'mounted',
                    navigate: (route) => pane.routing.navigate(route, { pushState: false, force: true, presentation: 'background' }),
                    reportFailure: (error) => reportNavigationEventFailure({ errorHandler: this.errorHandler }, 'Navigation failed on language change', error)
                }),

            captureFocusIntent: (_request, pane) => {
                if (this.pagePanes.getFocusedPane() !== pane) return null;
                const intent = this.pagePanes.claimFocusIntent();
                this.#browserNavigation.markNavigation(intent);
                return intent;
            },
            executeNavigation: (request, signal, pane) => {
                this.pagePanes.navigation.restoration.noteRequest(request);
                this.pagePanes.navigation.reflow.noteRequest(request);
                return executeRoutePaneNavigation(
                    {
                        pane,
                        pagePanes: this.pagePanes,
                        browserNavigation: this.#browserNavigation,
                        router: this,
                        auth: this.auth,
                        navigationMiddleware: this.navigationMiddleware,
                        componentLoader: this.#componentLoader,
                        lifecycle: this.#lifecycleDependencies,
                        sectionTracker: this.sectionTracker,
                        sidebarTargets: this.#sidebarTargets,
                        getSidebarService: this.#getSidebarService
                    },
                    request,
                    signal
                );
            },
            parseRoute: (path) => this.parseRoute(path),
            getDefaultRoute: () => this.getDefaultRoute(),
            back: () => this.back(),
            resolveTarget: (target) => {
                const request = normalizeNavigationRequest(target);
                return resolveRouteDetails({ ensureInitialized: () => this.ensureInitialized(), path: request.path, route: request.route, parameters: request.parameters, parseRoute: (path) => this.parseRoute(path) });
            },
            replaceProjection: (path, title, previousRoute, pane) => {
                if (this.pagePanes.getFocusedPane() === pane) this.#browserNavigation.project(path, pane.id, 'replace', this.#browserNavigation.focusIntent, { previousRoute, title });
                this.pagePanes.persistence.changed();
            },
            reportFailure: (error) => {
                if (!claimErrorReporting(error)) return;
                notifyHandledOperationError(error);
                this.errorHandler.error('Router', 'Pane navigation failed', error);
            }
        });
    }
    get #focusedPane(): RoutePane {
        return this.pagePanes.getFocusedPane() ?? this.pagePanes.getPanes()[0] ?? this.#primaryPane;
    }
    get pageOutlet(): PageOutletService {
        return this.#focusedPane.outlet;
    }
    get pageHost(): { getCurrent: PageHostInstance['getCurrent'] } | null {
        return this.contentContainer ? ensurePageHost(this.pageOutlet) : null;
    }
    get currentRoute(): string | null {
        return this.#focusedPane.currentRoute;
    }
    set currentRoute(route: string | null) {
        this.#focusedPane.currentRoute = route;
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
            this.resources.track(this.pagePanes.subscribeFocusIntent((intent) => this.#browserNavigation.claim(intent)));
            this.resources.track(
                this.pagePanes.subscribeFocus((userIntent) => {
                    const pane = this.#focusedPane;
                    if (!pane.presentation.isFocused()) return;
                    const route = pane.currentRoute;
                    const parsed = route ? this.parseRoute(route) : null;
                    const generation = pane.outlet.getPageHost().getCurrentMountScope()?.generation ?? null;
                    if (parsed && route && (this.#focusedProjection?.paneId !== pane.id || this.#focusedProjection.route !== route || this.#focusedProjection.generation !== generation)) {
                        this.#focusedProjection = { paneId: pane.id, route, generation };
                        projectFocusedPane(this.#lifecycleDependencies, parsed.route, parsed.parameters, { paneId: pane.id, mountGeneration: generation, focused: true }, () => pane.presentation.isFocused() && this.pagePanes.getFocusedPane() === pane && pane.currentRoute === route && pane.outlet.getPageHost().getCurrentMountScope()?.generation === generation);
                        if (this.#focusedProjection.paneId !== pane.id || this.#focusedProjection.route !== route || this.#focusedProjection.generation !== generation) return;
                        updateSidebarActiveState(parsed.route.component, this.#sidebarTargets, resolveSidebarService(this.#getSidebarService, isSidebarServiceContract));
                        this.sectionTracker.initialize();
                    }
                    if (route && userIntent) this.#browserNavigation.select(pane.id, route, parsed ? resolveRouteTitle(parsed.route) : '');
                })
            );
            registerRouterInitializationEvents({
                browserNavigation: this.#browserNavigation,
                resources: this.resources,
                getWindow,
                errorHandler: this.errorHandler,
                renderCriticalError: (message: string) => renderRouterError(this.dom, this.contentContainer, 'critical', message, reloadHandler),
                refreshLanguage: () => {
                    for (const pane of this.pagePanes.getPanes()) pane.localization.request();
                },
                resumeLanguageRefresh: () => {
                    for (const pane of this.pagePanes.getPanes()) pane.localization.resume();
                }
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
        this.pagePanes.attach(resolved, this.pagePanes.getPanes()[0] ?? this.#primaryPane);
        this.contentContainer = resolved;
        this.dom.setStyle(this.contentContainer, 'opacity', null);
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
    readonly parseRoute = (routePath: string): { route: RouteEntry; parameters: RouteParameters } | null => {
        return parseRoutePath(routePath, this.routes, this.dynamicRoutes);
    };
    getDefaultRoute(): string {
        return resolveDefaultAuthenticatedRoute(this.storage.getDefaultPage(), this.auth);
    }
    back(): void {
        this.ensureInitialized();
        getHistory().back();
    }
    async navigate(target: string | NavigationTarget, options: NavigationOptions = {}): Promise<void> {
        return this.routerBoundary.execute(() => this.#focusedPane.navigate(normalizeNavigationRequest(target, options)), 'navigate');
    }
    async navigateBrowser(target: string, options: NavigationOptions, intent: BrowserNavigationTarget): Promise<void> {
        const pane = this.pagePanes.getPanes().find((candidate) => candidate.id === intent.paneId && !candidate.isDisposed) ?? this.#focusedPane;
        return this.routerBoundary.execute(() => pane.navigate(normalizeNavigationRequest(target, options), intent.focusIntent), 'navigate');
    }
    invalidateSession(): void {
        this.pagePanes.invalidateSession();
    }
    setBrowserNavigationSuspended(suspended: boolean): void {
        this.#browserNavigationSuspended = suspended;
        if (!suspended) for (const pane of this.pagePanes.getPanes()) pane.localization.resume();
    }
    getLatestNavigationCompletion(): Promise<void> | null {
        return this.#focusedPane.getLatestNavigationCompletion();
    }
    isBrowserNavigationSuspended(): boolean {
        return this.#browserNavigationSuspended;
    }
    useNavigationMiddleware(middleware: RouterMiddleware, options: { priority: number }): () => void {
        return useRouterNavigationMiddleware(this.navigationMiddleware, middleware, options);
    }
    beforeNavigate(callback: (route: RouteDefinition, parameters: RouteParameters, context: NavigationContext) => Promise<NavigationResultType | boolean | void | null>): () => void {
        const middleware = createBeforeNavigateMiddleware(callback);
        return this.useNavigationMiddleware(middleware, { priority: 10 });
    }
    getCurrentRoute(): string | null {
        return this.currentRoute;
    }
    replaceCurrentRoute(target: string | NavigationTarget): void {
        this.#focusedPane.routing.replaceCurrentRoute(target);
    }
    getRouteParameters(): RouteParameters {
        return this.#focusedPane.routing.getRouteParameters();
    }
    async reload(): Promise<void> {
        if (this.currentRoute) {
            await this.navigate(this.currentRoute, { pushState: false, force: true });
        }
    }
    async destroyCurrentPage(): Promise<void> {
        const outcomes = await Promise.allSettled(this.pagePanes.getPanes().map((pane) => pane.outlet.destroyCurrent({ force: true })));
        const failures = outcomes.flatMap((outcome) => (outcome.status === 'rejected' ? [ensureError(outcome.reason)] : []));
        if (failures.length) throw new AggregateError(failures, 'Workspace page destruction incomplete');
        await this.cleanupManager.cleanupAll();
    }

    async destroy(): Promise<void> {
        const panes = this.pagePanes.getPanes();
        const failures: Error[] = [];
        for (const pane of panes) runCleanupStepCollectingFailure(() => pane.disposeNavigation(), failures);
        const tasks = panes.map(async (pane) => (isFunction(pane.outlet.destroy) ? pane.outlet.destroy() : pane.outlet.destroyCurrent({ force: true })));
        tasks.push(Promise.resolve().then(() => this.resources.cleanup({ requireComplete: true })));
        const outcomes = await Promise.allSettled(tasks);
        failures.push(...outcomes.flatMap((outcome) => (outcome.status === 'rejected' ? [ensureError(outcome.reason)] : [])));
        if (failures.length) throw new AggregateError(failures, 'Workspace destruction incomplete');
        await this.pagePanes.detach();
        await this.cleanupManager.cleanupAll();
        this.sectionTracker.cleanup();
        this.currentRoute = null;
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
        return this.#focusedPane.routing.getQueryParameters();
    }
}

export { Router };
