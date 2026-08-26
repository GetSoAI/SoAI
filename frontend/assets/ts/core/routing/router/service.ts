/* SoAI - Shared routing router service [frontend/assets/ts/core/routing/router/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { getHeaderActions } from '@core/headeractions/public.ts';
import { NAVIGATION_STATUS, type NavigationResultType } from '@core/navigationMiddleware.ts';
import { createNavigationContext, shouldSkipNavigation } from '@core/routing/router/actions.ts';
import { normalizeMiddlewareOutcome } from '@core/routing/router/navigationMiddlewareNormalization.ts';
import { dispatchNavigationEvent, performNavigationCleanup, pushRouteState, updateBodyPageClass, updateSidebarActiveState, type RouterLifecycleDependencies } from '@core/routing/router/pageOutlet.ts';
import type { PageOutletService, RouterDependencies, SidebarServiceContract } from '@core/routing/router/routerDependencies.ts';
import type { NavigationConnectionHoldToken } from '@core/routing/router/routerConnectionHold.ts';
import type { NavigationDetail, NavigationContext, NavigationOptions, NavigationRequest, NavigationRouterHost, RouteDefinition, RouteEntry, RouteParameters, SidebarComponentTargets } from '@core/routing/router/types.ts';
import { filterStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isAbortError, raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';

const REDIRECT_CHAIN_META_KEY = '__soaiRedirectChain';
const MAX_REDIRECT_DEPTH = 8;

const startHeaderActionHandoffs = (route: RouteDefinition): string[] => {
    const actionIds = route.layout.headerActionHandoff;
    if (!actionIds.length) {
        return [];
    }
    const headerActions = getHeaderActions();
    actionIds.forEach((actionId) => headerActions.startActionHandoff(actionId));
    return actionIds.slice();
};

const endHeaderActionHandoffs = (actionIds: readonly string[]): void => {
    if (!actionIds.length) {
        return;
    }
    const headerActions = getHeaderActions();
    actionIds.forEach((actionId) => headerActions.endActionHandoff(actionId));
};

const getRedirectChain = (request: NavigationRequest): string[] => {
    const metaValue = request.meta;
    if (!isObject(metaValue)) {
        return [];
    }
    const chainValue = metaValue[REDIRECT_CHAIN_META_KEY];
    return filterStringArrayValue(chainValue).filter(Boolean);
};

interface RouterApplyRouteState {
    currentRoute: string | null;
    setCurrentRoute: (route: string) => void;
    setLastNavigationDetail: (detail: NavigationDetail | null) => void;
}

interface RouterConnectionHoldPort {
    acquire: () => NavigationConnectionHoldToken;
    release: (token: NavigationConnectionHoldToken) => boolean;
}

interface RouterApplyRouteDependencies {
    lifecycle: RouterLifecycleDependencies;
    request: NavigationRequest & { targetPath: string };
    resolvedRoute: RouteDefinition;
    resolvedParameters: RouteParameters;
    state: RouterApplyRouteState;
    sectionTracker: { initialize: () => void };
    preloadDependencies: (route: RouteDefinition) => Promise<void>;
    loadPageComponent: (componentName: string, parameters: RouteParameters, options: { beforePrepare: () => Promise<void>; beforeCommit: () => Promise<void>; commitNavigation: () => void; signal: AbortSignal }) => Promise<boolean>;
    sidebarTargets: SidebarComponentTargets;
    resolveSidebarService: () => SidebarServiceContract | null;
    historyApi: History;
    routeTitle: string;
    connectionHold: RouterConnectionHoldPort;
    signal: AbortSignal;
}

interface RouterExecuteNavigationDependencies {
    router: NavigationRouterHost | null;
    state: RouterApplyRouteState;
    request: NavigationRequest;
    parseRoute: (path: string) => { route: RouteEntry; parameters: RouteParameters } | null;
    resolveRouteDetails: (path: string, route: RouteDefinition | null, parameters: RouteParameters | null) => { path: string; route: RouteDefinition; parameters: RouteParameters };
    validateNavigation: (route: RouteDefinition) => void;
    runNavigationMiddleware: (context: NavigationContext) => Promise<NavigationResultType>;
    preloadDependencies: (route: RouteDefinition) => Promise<void>;
    pageOutlet: PageOutletService;
    redirect: (target: string, options: NavigationOptions) => Promise<void>;
    lifecycle: RouterLifecycleDependencies;
    sectionTracker: { initialize: () => void };
    loadPageComponent: (componentName: string, parameters: RouteParameters, options: { beforePrepare: () => Promise<void>; beforeCommit: () => Promise<void>; commitNavigation: () => void; signal: AbortSignal }) => Promise<boolean>;
    sidebarTargets: SidebarComponentTargets;
    resolveSidebarService: () => SidebarServiceContract | null;
    historyApi: History;
    resolveRouteTitle: (route: RouteDefinition) => string;
    connectionHold: RouterConnectionHoldPort;
    signal: AbortSignal;
}

const createRouterLifecycleDependencies = (options: { dom: RouterDependencies['dom']; stateManager: RouterDependencies['state']; cleanupManager: RouterDependencies['cleanupManager']; closeOpenModals: () => number; queryUI: (selector: string) => Element[]; emitRouterEvent: (stage: string, data?: Record<string, JsonValue>, severity?: string) => void }): RouterLifecycleDependencies => {
    return {
        dom: options.dom,
        stateManager: options.stateManager,
        cleanupManager: options.cleanupManager,
        closeOpenModals: options.closeOpenModals,
        queryUI: options.queryUI,
        emitRouterEvent: options.emitRouterEvent
    };
};

const applyResolvedRoute = async (dependencies: RouterApplyRouteDependencies): Promise<boolean> => {
    const { lifecycle, request, resolvedRoute, resolvedParameters, state, sectionTracker, loadPageComponent, sidebarTargets, resolveSidebarService, historyApi, routeTitle, connectionHold, signal } = dependencies;
    throwIfAborted(signal);
    lifecycle.emitRouterEvent('applyRoute:start', {
        route: resolvedRoute.path || null,
        component: resolvedRoute.component || null
    });
    const token = connectionHold.acquire();
    const headerActionHandoffs = startHeaderActionHandoffs(resolvedRoute);
    let routeStateCommitted = false;
    try {
        await raceWithAbortSignal(performNavigationCleanup(lifecycle, state.currentRoute), signal);

        state.setLastNavigationDetail(dispatchNavigationEvent(lifecycle, resolvedRoute, resolvedParameters, 'start', null));

        lifecycle.emitRouterEvent('component:load:start', {
            component: resolvedRoute.component,
            route: resolvedRoute.path || null
        });
        const pageCommitted = await loadPageComponent(resolvedRoute.component, resolvedParameters, {
            beforePrepare: async (): Promise<void> => dependencies.preloadDependencies(resolvedRoute),
            beforeCommit: async (): Promise<void> => lifecycle.cleanupManager.cleanupAll(),
            commitNavigation: (): void => {
                updateBodyPageClass(lifecycle, resolvedRoute);
                updateSidebarActiveState(resolvedRoute.component, sidebarTargets, resolveSidebarService());
                if (request.pushState) pushRouteState(historyApi, request.targetPath, routeTitle, request.replaceState);
                state.setCurrentRoute(request.targetPath);
                sectionTracker.initialize();
                state.setLastNavigationDetail(dispatchNavigationEvent(lifecycle, resolvedRoute, resolvedParameters, 'complete', null));
                routeStateCommitted = true;
            },
            signal
        });
        if (!pageCommitted && !routeStateCommitted) {
            return false;
        }
        if (!routeStateCommitted) throw new Error(`Page ${resolvedRoute.component} committed without route state`);
        lifecycle.emitRouterEvent('component:load:ready', {
            component: resolvedRoute.component,
            route: resolvedRoute.path || null
        });

        return true;
    } catch (error) {
        const runtimeError = ensureError(error);
        if (isAbortError(runtimeError) && signal.aborted) return false;
        state.setLastNavigationDetail(dispatchNavigationEvent(lifecycle, resolvedRoute, resolvedParameters, 'error', runtimeError));
        throw runtimeError;
    } finally {
        endHeaderActionHandoffs(headerActionHandoffs);
        connectionHold.release(token);
        lifecycle.emitRouterEvent('applyRoute:complete', {
            route: resolvedRoute.path || null,
            component: resolvedRoute.component || null
        });
    }
};

const executeNavigationRequest = async (dependencies: RouterExecuteNavigationDependencies): Promise<void> => {
    const details = dependencies.resolveRouteDetails(dependencies.request.path, dependencies.request.route, dependencies.request.parameters);
    const targetPath = details.path;
    const resolvedRoute = details.route;
    const resolvedParameters = details.parameters;

    if (!dependencies.request.force && shouldSkipNavigation(dependencies.state.currentRoute, targetPath, dependencies.pageOutlet)) {
        return;
    }
    dependencies.validateNavigation(resolvedRoute);

    const context = createNavigationContext({
        router: dependencies.router,
        currentRoute: dependencies.state.currentRoute,
        parseRoute: dependencies.parseRoute,
        request: dependencies.request,
        route: resolvedRoute,
        parameters: resolvedParameters,
        signal: dependencies.signal
    });

    try {
        const outcome = normalizeMiddlewareOutcome(await raceWithAbortSignal(dependencies.runNavigationMiddleware(context), dependencies.signal));
        if (outcome.status === NAVIGATION_STATUS.BLOCKED) {
            return;
        }
        if (outcome.status === NAVIGATION_STATUS.REDIRECT) {
            const redirectChain = [...getRedirectChain(dependencies.request), targetPath];
            if (redirectChain.length > MAX_REDIRECT_DEPTH) {
                throw new Error(`Router redirect depth exceeded ${MAX_REDIRECT_DEPTH}`);
            }
            if (redirectChain.includes(outcome.target)) {
                throw new Error(`Router detected redirect loop for route: ${outcome.target}`);
            }
            const redirectOptions = { ...outcome.options };
            const existingMeta = isObject(redirectOptions['meta']) ? redirectOptions['meta'] : {};
            redirectOptions['meta'] = {
                ...existingMeta,
                [REDIRECT_CHAIN_META_KEY]: redirectChain
            };
            await dependencies.redirect(outcome.target, redirectOptions);
            return;
        }
        await applyResolvedRoute({
            lifecycle: dependencies.lifecycle,
            request: { ...dependencies.request, targetPath },
            resolvedRoute,
            resolvedParameters,
            state: dependencies.state,
            sectionTracker: dependencies.sectionTracker,
            preloadDependencies: dependencies.preloadDependencies,
            loadPageComponent: dependencies.loadPageComponent,
            sidebarTargets: dependencies.sidebarTargets,
            resolveSidebarService: dependencies.resolveSidebarService,
            historyApi: dependencies.historyApi,
            routeTitle: dependencies.resolveRouteTitle(resolvedRoute),
            connectionHold: dependencies.connectionHold,
            signal: dependencies.signal
        });
    } catch (error) {
        if (isAbortError(error) && dependencies.signal.aborted) return;
        throw error;
    }
};

export { applyResolvedRoute, createRouterLifecycleDependencies, executeNavigationRequest, MAX_REDIRECT_DEPTH };
export type { RouterApplyRouteDependencies, RouterApplyRouteState, RouterExecuteNavigationDependencies };
