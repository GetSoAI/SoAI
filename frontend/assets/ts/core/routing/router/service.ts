/* SoAI - Shared routing router service [frontend/assets/ts/core/routing/router/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { getHeaderActions } from '@core/headeractions/public.ts';
import { NAVIGATION_STATUS } from '@core/navigationMiddleware.ts';
import type { NavigationResultType, NavigationDetail, NavigationContext, NavigationOptions, NavigationPlacementAdmission, NavigationRequest, NavigationRouterHost, RouteDefinition, RouteEntry, RouteParameters, SidebarComponentTargets, PageMountPresentation, PageMountScope, NavigationProtectionApproval } from '@core/routing/router/types.ts';
import { createNavigationContext, createDestructionNavigationContext, shouldSkipNavigation } from '@core/routing/router/actions.ts';
import { normalizeMiddlewareOutcome } from '@core/routing/router/navigationMiddlewareNormalization.ts';
import { dispatchNavigationEvent, performNavigationCleanup, updateBodyPageClass, updateSidebarActiveState, type RouterLifecycleDependencies } from '@core/routing/router/pageOutlet.ts';
import type { RouterDependencies, SidebarServiceContract } from '@core/routing/router/routerDependencies.ts';
import type { PageOutletService } from '@core/pageoutlet/types.ts';
import type { NavigationConnectionHoldToken } from '@core/routing/router/routerConnectionHold.ts';

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PageHostCommitOptions } from '@core/pagehost/types.ts';

import { createAbortError, isAbortError, raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { resolveNavigationDestructionOwner } from '@core/navigationGuards.ts';

import { createDeferred } from '@core/runtime/deferred.ts';
import { reportPagePaneActionFailure } from '@core/pagepanes/notifications.ts';
import { createNavigationRedirectOptions, MAX_REDIRECT_DEPTH } from '@core/routing/router/navigationRedirects.ts';
import { evaluatePlacementDestruction, admitPlacementDestruction, commitPlacementClose } from '@core/routing/router/middlewares/dirtyStateMiddleware.ts';

const startHeaderActionHandoffs = (route: RouteDefinition, state: RouterApplyRouteState): Array<() => void> => {
    const owner = state.currentMountScope;
    if (!owner) return [];
    const releases: Array<() => void> = [];
    try {
        for (const actionId of route.layout.headerActionHandoff) releases.push(getHeaderActions().startActionHandoff(actionId, owner, state.presentation));
        return releases;
    } catch (error) {
        const failures = [ensureError(error)];
        for (const release of releases) runCleanupStepCollectingFailure(release, failures);
        throw new AggregateError(failures, 'Header handoff acquisition failed');
    }
};

interface RouterApplyRouteState {
    presentation: PageMountPresentation;
    currentMountScope: PageMountScope | null;
    currentRoute: string | null;
    setCurrentRoute: (route: string | null) => void;
    setLastNavigationDetail: (detail: NavigationDetail | null) => void;
}

interface RouterConnectionHoldPort {
    acquire: () => NavigationConnectionHoldToken;
    release: (token: NavigationConnectionHoldToken) => boolean;
}

interface RouterPageRenderOptions {
    routePath: string;
    beforePrepare: () => Promise<void>;
    beforeCommit?: (() => Promise<void>) | undefined;
    finalAdmission?: (() => void) | undefined;
    mountPublication: NonNullable<PageHostCommitOptions['mountPublication']>;
    afterCommit: (previousContainer: HTMLElement | null) => Promise<void>;
    commitNavigation: () => void;
    signal: AbortSignal;
}

interface RouterApplyRouteDependencies {
    beforeCommit?: (() => Promise<void>) | undefined;
    finalAdmission?: (() => void) | undefined;
    lifecycle: RouterLifecycleDependencies;
    request: NavigationRequest & { targetPath: string };
    resolvedRoute: RouteDefinition;
    resolvedParameters: RouteParameters;
    state: RouterApplyRouteState;
    sectionTracker: { initialize: () => void };
    preloadDependencies: (route: RouteDefinition) => Promise<void>;
    loadPageComponent: (componentName: string, parameters: RouteParameters, options: RouterPageRenderOptions) => Promise<boolean>;
    sidebarTargets: SidebarComponentTargets;
    resolveSidebarService: () => SidebarServiceContract | null;
    projectHistory: (route: string, title: string, mode: 'push' | 'replace' | 'preserve') => void;
    routeTitle: string;
    connectionHold: RouterConnectionHoldPort;
    signal: AbortSignal;
}

interface RouterExecuteNavigationDependencies {
    admitPlacement?: NavigationContext['admitPlacement'] | undefined;
    authEpoch: number;
    router: NavigationRouterHost | null;
    state: RouterApplyRouteState;
    parseRoute: (path: string) => { route: RouteEntry; parameters: RouteParameters } | null;
    resolveRouteDetails: (path: string, route: RouteDefinition | null, parameters: RouteParameters | null) => { path: string; route: RouteDefinition; parameters: RouteParameters };
    validateNavigation: (route: RouteDefinition) => void;
    runNavigationMiddleware: (context: NavigationContext) => Promise<NavigationResultType>;
    preloadDependencies: (route: RouteDefinition) => Promise<void>;
    pageOutlet: PageOutletService;
    redirect: (target: string, options: NavigationOptions) => Promise<void>;
    lifecycle: RouterLifecycleDependencies;
    sectionTracker: { initialize: () => void };
    loadPageComponent: (componentName: string, parameters: RouteParameters, options: RouterPageRenderOptions) => Promise<boolean>;
    sidebarTargets: SidebarComponentTargets;
    resolveSidebarService: () => SidebarServiceContract | null;
    projectHistory: RouterApplyRouteDependencies['projectHistory'];
    repairHistory: () => void;
    resolveRouteTitle: (route: RouteDefinition) => string;
    connectionHold: RouterConnectionHoldPort;
}

const createRouterLifecycleDependencies = (options: { dom: RouterDependencies['dom']; stateManager: RouterDependencies['state']; cleanupManager: RouterDependencies['cleanupManager']; closeOpenModals: (owner: PageMountScope | null) => number; queryUI: (selector: string) => Element[]; emitRouterEvent: (stage: string, data?: Record<string, JsonValue>, severity?: string) => void }): RouterLifecycleDependencies => {
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
    const { lifecycle, request, resolvedRoute, resolvedParameters, state, sectionTracker, loadPageComponent, sidebarTargets, resolveSidebarService, projectHistory, routeTitle, connectionHold, signal } = dependencies;
    throwIfAborted(signal);
    lifecycle.emitRouterEvent('applyRoute:start', {
        route: resolvedRoute.path || null,
        component: resolvedRoute.component || null
    });
    const outgoingOwner = state.currentMountScope;
    const token = connectionHold.acquire();
    let headerActionHandoffs: Array<() => void> = [];
    let routeStateCommitted = false;
    let previousRoute: string | null = null;
    let historyProjected = false;
    const projectCommittedHistory = (): void => {
        if (historyProjected || !routeStateCommitted || !state.presentation.isFocused()) return;
        historyProjected = true;
        projectHistory(request.targetPath, routeTitle, request.pushState ? (request.replaceState ? 'replace' : 'push') : 'preserve');
    };
    try {
        headerActionHandoffs = startHeaderActionHandoffs(resolvedRoute, state);
        state.setLastNavigationDetail(dispatchNavigationEvent(lifecycle, resolvedRoute, resolvedParameters, 'start', null));

        lifecycle.emitRouterEvent('component:load:start', {
            component: resolvedRoute.component,
            route: resolvedRoute.path || null
        });
        const pageCommitted = await loadPageComponent(resolvedRoute.component, resolvedParameters, {
            routePath: request.targetPath,
            beforeCommit: dependencies.beforeCommit,
            finalAdmission: dependencies.finalAdmission,
            mountPublication: {
                commit: () => {
                    previousRoute = state.currentRoute;
                    state.setCurrentRoute(request.targetPath);
                    routeStateCommitted = true;
                },
                rollback: () => {
                    state.setCurrentRoute(previousRoute);
                    routeStateCommitted = false;
                }
            },
            beforePrepare: async (): Promise<void> => dependencies.preloadDependencies(resolvedRoute),
            afterCommit: async (): Promise<void> => {
                projectCommittedHistory();
                await performNavigationCleanup(lifecycle, previousRoute, outgoingOwner);
            },
            commitNavigation: (): void => {
                if (state.presentation.isFocused()) {
                    updateBodyPageClass(lifecycle, resolvedRoute);
                    updateSidebarActiveState(resolvedRoute.component, sidebarTargets, resolveSidebarService());
                    projectCommittedHistory();
                    sectionTracker.initialize();
                }
                state.setLastNavigationDetail(dispatchNavigationEvent(lifecycle, resolvedRoute, resolvedParameters, 'complete', null, state.presentation.isFocused()));
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
        const failures: Error[] = [];
        for (const release of headerActionHandoffs) runCleanupStepCollectingFailure(release, failures);
        runCleanupStepCollectingFailure(() => {
            connectionHold.release(token);
        }, failures);
        runCleanupStepCollectingFailure(() => lifecycle.emitRouterEvent('applyRoute:complete', { route: resolvedRoute.path || null, component: resolvedRoute.component || null }), failures);
        throwCollectedCleanupFailures(failures);
    }
};

const executeNavigationRequest = async (dependencies: RouterExecuteNavigationDependencies, request: NavigationRequest, signal: AbortSignal): Promise<void> => {
    const details = dependencies.resolveRouteDetails(request.path, request.route, request.parameters);
    const targetPath = details.path;
    const resolvedRoute = details.route;
    const resolvedParameters = details.parameters;

    dependencies.validateNavigation(resolvedRoute);

    const currentOwner = dependencies.state.currentMountScope;
    const destructionOwner = resolveNavigationDestructionOwner(currentOwner, dependencies.authEpoch);
    const requestAdmission: { placement: NavigationPlacementAdmission | null; pending: Promise<NavigationPlacementAdmission> | null; finished: boolean; destructionApprovals: NavigationProtectionApproval[] } = { placement: null, pending: null, finished: false, destructionApprovals: [] };
    const context = createNavigationContext({
        admitPlacement: async (candidateContext) => {
            throwIfAborted(signal);
            if (requestAdmission.pending) return requestAdmission.pending;
            const completion = createDeferred<NavigationPlacementAdmission>();
            requestAdmission.pending = completion.promise;
            const admit = async (): Promise<NavigationPlacementAdmission> => {
                throwIfAborted(signal);
                if (requestAdmission.finished) throw createAbortError('Navigation no longer owns placement admission');
                let placement: NavigationPlacementAdmission;
                if (dependencies.admitPlacement) placement = await dependencies.admitPlacement(candidateContext);
                else {
                    const owner = resolveNavigationDestructionOwner(dependencies.state.currentMountScope, dependencies.authEpoch);
                    const retained = !request.force && owner !== null && owner.admission.isActive() && shouldSkipNavigation(dependencies.state.currentRoute, targetPath, dependencies.pageOutlet);
                    const guardContext = createDestructionNavigationContext(candidateContext, dependencies.state.currentRoute, owner, dependencies.parseRoute);
                    placement = { type: retained ? 'retained' : 'render', guardContexts: retained ? [] : [guardContext] };
                }
                if (requestAdmission.finished) {
                    placement.settle?.();
                    throw createAbortError('Navigation placement completed after its request');
                }
                requestAdmission.placement = placement;
                if (placement.type === 'retained' && placement.guardContexts.length) throw new Error('Retained navigation cannot admit page destruction');
                return placement;
            };
            void Promise.resolve()
                .then(admit)
                .then(completion.resolve, (error) => completion.reject(ensureError(error)));
            return completion.promise;
        },
        approveDestruction: (approval) => {
            requestAdmission.destructionApprovals.push(approval);
        },
        destructionOwner,
        router: dependencies.router,
        currentRoute: dependencies.state.currentRoute,
        parseRoute: dependencies.parseRoute,
        request: request,
        route: resolvedRoute,
        parameters: resolvedParameters,
        signal: signal
    });

    try {
        const outcome = normalizeMiddlewareOutcome(await raceWithAbortSignal(dependencies.runNavigationMiddleware(context), signal));
        throwIfAborted(signal);
        if (outcome.status === NAVIGATION_STATUS.BLOCKED) {
            throwIfAborted(signal);
            if (!request.pushState) dependencies.repairHistory();
            if (outcome.failure) {
                if (request.intent === 'close' || request.intent === 'restore') throw outcome.failure;
                reportPagePaneActionFailure(outcome.failure);
            }
            return;
        }
        if (outcome.status === NAVIGATION_STATUS.REDIRECT) {
            await dependencies.redirect(outcome.target, createNavigationRedirectOptions(request, targetPath, outcome.target, outcome.options));
            return;
        }
        const placement = requestAdmission.placement;
        if (!placement) throw new Error('Navigation continued without placement admission');
        if (placement.type === 'retained') {
            placement.finalAdmission?.();
            placement.complete?.();
            return;
        }
        if (placement.type === 'close') {
            await commitPlacementClose(placement, requestAdmission.destructionApprovals, signal, dependencies.repairHistory);
            return;
        }
        if (placement.guardPhase !== 'before-commit' && requestAdmission.destructionApprovals.length !== placement.guardContexts.length) throw new Error('Navigation continued without destruction approval');
        const deferredGuard: { verdict: NavigationResultType | null } = { verdict: null };
        const committed = await applyResolvedRoute({
            beforeCommit:
                placement.guardPhase === 'before-commit'
                    ? async () => {
                          deferredGuard.verdict = await evaluatePlacementDestruction(placement);
                          throwIfAborted(signal);
                          if (deferredGuard.verdict !== null) throw createAbortError('Navigation destruction guard refused the prepared page');
                      }
                    : undefined,
            finalAdmission: () => admitPlacementDestruction(placement, requestAdmission.destructionApprovals, signal),
            lifecycle: dependencies.lifecycle,
            request: { ...request, targetPath },
            resolvedRoute,
            resolvedParameters,
            state: dependencies.state,
            sectionTracker: dependencies.sectionTracker,
            preloadDependencies: dependencies.preloadDependencies,
            loadPageComponent: dependencies.loadPageComponent,
            sidebarTargets: dependencies.sidebarTargets,
            resolveSidebarService: dependencies.resolveSidebarService,
            projectHistory: dependencies.projectHistory,
            routeTitle: dependencies.resolveRouteTitle(resolvedRoute),
            connectionHold: dependencies.connectionHold,
            signal: signal
        });
        if (deferredGuard.verdict?.status === NAVIGATION_STATUS.REDIRECT) {
            requestAdmission.finished = true;
            requestAdmission.placement = null;
            placement.settle?.();
            await dependencies.redirect(deferredGuard.verdict.target, createNavigationRedirectOptions(request, targetPath, deferredGuard.verdict.target, deferredGuard.verdict.options));
            return;
        }
        if (!committed && !signal.aborted && !request.pushState) dependencies.repairHistory();
        if (committed && !signal.aborted) placement.complete?.();
    } catch (error) {
        if (isAbortError(error) && signal.aborted) return;
        throw error;
    } finally {
        requestAdmission.finished = true;
        requestAdmission.placement?.settle?.();
    }
};

export { applyResolvedRoute, createRouterLifecycleDependencies, executeNavigationRequest, MAX_REDIRECT_DEPTH };
export type { RouterPageRenderOptions, RouterApplyRouteDependencies, RouterApplyRouteState, RouterExecuteNavigationDependencies };
