/* SoAI - Shared routing router composition [frontend/assets/ts/core/routing/router/routerComposition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createNavigationMiddlewareController } from '@core/navigationMiddleware.ts';
import { PageContext } from '@core/pagecontext/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { RouterComponentLoader } from '@core/routing/router/componentLoader.ts';
import { normalizeNavigationRequest } from '@core/routing/router/navigationRequest.ts';
import { createReloadHandler } from '@core/routing/router/pageOutlet.ts';
import { resolveRouteDetails } from '@core/routing/router/actions.ts';
import { createRouterLifecycleDependencies } from '@core/routing/router/service.ts';
import { registerCoreNavigationMiddleware, useRouterNavigationMiddleware } from '@core/routing/router/guards.ts';
import type { RouterDependencies } from '@core/routing/router/routerDependencies.ts';
import type { NavigationTarget, RouteDefinition, RouteParameters } from '@core/routing/router/types.ts';
import type { RouterHost } from '@core/routing/router/routerHost.ts';
import { getLocation } from '@core/environment/public.ts';
import { telemetry } from '@core/telemetry/service.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';

const emitRouterEvent = (stage: string, data: Record<string, JsonValue | null | undefined> = {}, severity: string = 'info'): void => {
    telemetry.emit({ module: 'Router', stage, severity, message: stage, data });
};

const createRouterComposition = (router: RouterHost, dependencies: RouterDependencies) => {
    const { dom, storage, auth, api, streamManager, state, cleanupManager, ResourceTracker, errorHandler, PageOutlet, ErrorBoundary, modalPresenter, componentRegistry, pageRegistry, getSidebarService } = dependencies;
    const pageContext = new PageContext({ pageId: 'router' });
    const pageOutlet = new PageOutlet({
        emitEvent: emitRouterEvent,
        onPreservedPageFailure: () => pageContext.notifications.error(i18n.t('common.errors.operationFailed')),
        onRetry: () => terminateHandledPromise(router.reload()),
        pageRegistry
    });
    const resources = new ResourceTracker();
    const routerBoundary = new ErrorBoundary('Router');
    const navigationMiddleware = createNavigationMiddlewareController();
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
        closeOpenModals: () => modalPresenter.closeAll({ force: true, restoreFocus: false, reason: 'navigation' }),
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
        pageOutlet,
        resources,
        routerBoundary,
        navigationMiddleware,
        componentRegistry,
        getSidebarService,
        componentLoader,
        lifecycleDependencies
    };
};

const reloadHandler = createReloadHandler(getLocation);

export { createRouterComposition, emitRouterEvent, reloadHandler };
