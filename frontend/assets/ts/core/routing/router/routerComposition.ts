/* SoAI - Shared routing router composition [frontend/assets/ts/core/routing/router/routerComposition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createNavigationMiddlewareController } from '@core/navigationMiddleware.ts';
import { PageContext } from '@core/pagecontext/public.ts';
import { resolveErrorState } from '@core/pageoutlet/actions.ts';
import { RouterComponentLoader } from '@core/routing/router/componentLoader.ts';
import { normalizeNavigationRequest } from '@core/routing/router/navigationRequest.ts';
import { createReloadHandler } from '@core/routing/router/pageOutlet.ts';
import { getRouteFromHash, resolveRouteDetails } from '@core/routing/router/actions.ts';
import { createRouterLifecycleDependencies } from '@core/routing/router/service.ts';
import { registerCoreNavigationMiddleware, useRouterNavigationMiddleware } from '@core/routing/router/guards.ts';
import type { RouterDependencies } from '@core/routing/router/routerDependencies.ts';
import type { NavigationTarget, RouteDefinition, RouteParameters } from '@core/routing/router/types.ts';
import type { RouterHost } from '@core/routing/router/routerHost.ts';
import { getLocation, getWindow } from '@core/environment/public.ts';
import { RouterBrowserNavigation } from '@core/routing/router/events.ts';
import { telemetry } from '@core/telemetry/service.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';
import { RouterLocalizationRefreshController, type RouterLocalizationHost } from '@core/routing/router/localizationRefresh.ts';
import { ensureError } from '@core/errors/coerce.ts';

const emitRouterEvent = (stage: string, data: Record<string, JsonValue | null | undefined> = {}, severity: string = 'info'): void => {
    telemetry.emit({ module: 'Router', stage, severity, message: stage, data });
};

const createPaneResources = (dependencies: RouterDependencies, pageContext: PageContext, host: Omit<RouterLocalizationHost, 'hasOpenModals'>) => {
    const { PageOutlet, pageRegistry, errorHandler } = dependencies;
    const refreshFocusedProjection = (): void => {
        try {
            dependencies.pagePanes.refreshFocusedProjection();
        } catch (error) {
            errorHandler.warn('Router', 'Focused outlet projection failed', ensureError(error));
        }
    };
    const pageOutlet = new PageOutlet({
        onStateChanged: refreshFocusedProjection,
        emitEvent: emitRouterEvent,
        onPreservedPageFailure: (error) => {
            const state = resolveErrorState(error);
            pageContext.notifications.error(state.detail ?? state.label);
        },
        onRetry: () => {
            const route = host.getCurrentRoute();
            if (route) terminateHandledPromise(host.navigate(route));
        },
        pageRegistry,
        spinnerWorkerUrl: dependencies.spinnerWorkerUrl
    });
    return { outlet: pageOutlet, onNavigationSettled: refreshFocusedProjection, localization: new RouterLocalizationRefreshController({ ...host, hasOpenModals: () => dependencies.modalPresenter.hasOpenModals() }) };
};

const createRouterComposition = (router: RouterHost, dependencies: RouterDependencies) => {
    const { dom, storage, auth, api, streamManager, state, cleanupManager, ResourceTracker, errorHandler, ErrorBoundary, modalPresenter, componentRegistry, getSidebarService } = dependencies;
    const pageContext = new PageContext({ pageId: 'router' });
    const resources = new ResourceTracker();
    const routerBoundary = new ErrorBoundary('Router');
    const navigationMiddleware = createNavigationMiddlewareController();
    const browserNavigation = new RouterBrowserNavigation({
        getWindow,
        getRouteFromHash: () => router.getRouteFromHash(),
        parseHash: getRouteFromHash,
        parseRoute: (route) => router.parseRoute(route),
        getDefaultRoute: () => router.getDefaultRoute(),
        isBrowserNavigationSuspended: () => router.isBrowserNavigationSuspended(),
        claimFocusIntent: () => dependencies.pagePanes.claimFocusIntent(),
        isCurrentFocusIntent: (intent) => dependencies.pagePanes.isCurrentFocusIntent(intent),
        getFocusedPaneId: () => dependencies.pagePanes.getFocusedPane()?.id ?? null,
        navigate: (route, options, intent) => router.navigateBrowser(route, options, intent),
        errorHandler
    });
    const componentLoader = new RouterComponentLoader({
        dom,
        resources,
        streamManager,
        errorHandler,
        emitEvent: emitRouterEvent,
        isComponentRegistered: (name: string) => Boolean(name && componentRegistry.has(name)),
        normalizeNavigationRequest: (target: string | NavigationTarget) => normalizeNavigationRequest(target),
        resolveRouteDetails: (path: string, route: RouteDefinition | null, parameters: RouteParameters | null) =>
            resolveRouteDetails({
                ensureInitialized: () => router.ensureInitialized(),
                path,
                route,
                parameters,
                parseRoute: (targetPath: string) => router.parseRoute(targetPath)
            }),
        validateNavigation: (route: RouteDefinition) => {
            if (!route || !isString(route.component) || !route.component) {
                throw new Error('Route missing component');
            }
        }
    });
    const lifecycleDependencies = createRouterLifecycleDependencies({
        dom,
        stateManager: state,
        cleanupManager,
        closeOpenModals: (owner) => (owner ? modalPresenter.closeAll(owner, { force: true, restoreFocus: false, reason: 'navigation' }) : 0),
        queryUI: (selector: string) => dom.resolveAll(selector),
        emitRouterEvent
    });
    registerCoreNavigationMiddleware(
        {
            auth,
            storage,
            api,
            emitRouterEvent
        },
        (middleware, options) => useRouterNavigationMiddleware(navigationMiddleware, middleware, options)
    );
    return {
        dom,
        storage,
        auth,
        api,
        streamManager,
        stateManager: state,
        cleanupManager,
        sectionTracker: state.section,
        errorHandler,
        pageContext,
        notifications: pageContext.notifications,
        resources,
        routerBoundary,
        navigationMiddleware,
        browserNavigation,
        componentRegistry,
        getSidebarService,
        componentLoader,
        createPaneResources: (host: Omit<RouterLocalizationHost, 'hasOpenModals'>) => createPaneResources(dependencies, pageContext, host),
        lifecycleDependencies
    };
};

const reloadHandler = createReloadHandler(getLocation);

export { createRouterComposition, emitRouterEvent, reloadHandler };
