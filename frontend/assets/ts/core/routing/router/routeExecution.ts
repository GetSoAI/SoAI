/* SoAI - Pane navigation bindings for the shared middleware and mount pipeline [frontend/assets/ts/core/routing/router/routeExecution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { createPageMountScope } from '@core/routing/pages/basepagecore/pageMountScope.ts';
import type { RoutePane } from '@core/routing/router/RoutePane.ts';
import type { RouterComponentLoader } from '@core/routing/router/componentLoader.ts';
import { resolveRouteDetails } from '@core/routing/router/actions.ts';
import { normalizeNavigationRequest } from '@core/routing/router/navigationRequest.ts';
import { resolveRouteTitle } from '@core/routing/router/navigation.ts';
import { isSidebarServiceContract, resolveSidebarService } from '@core/routing/router/routerInternals.ts';
import { acquireNavigationConnectionHold, releaseNavigationConnectionHold } from '@core/routing/router/routerConnectionHold.ts';
import { runCommittedNavigationCleanup } from '@core/pageoutlet/actions.ts';
import { createRouterLifecycleDependencies, executeNavigationRequest, type RouterPageRenderOptions } from '@core/routing/router/service.ts';
import type { RouterDependencies } from '@core/routing/router/routerDependencies.ts';
import type { NavigationContext, NavigationOptions, NavigationRequest, RouteDefinition, RouteParameters, SidebarComponentTargets, PageRouting } from '@core/routing/router/types.ts';

import type { NavigationMiddlewareController } from '@core/navigationMiddleware.ts';
import type { PagePaneService } from '@core/pagepanes/service.ts';
import type { PagePaneAdmissionResult } from '@core/pagepanes/admission.ts';
import type { RouterBrowserNavigation } from '@core/routing/router/events.ts';
import { reportPagePaneRetirementOutcome } from '@core/pagepanes/notifications.ts';

interface RouteExecutionDependencies {
    pane: RoutePane;
    pagePanes: PagePaneService;
    browserNavigation: Pick<RouterBrowserNavigation, 'project'>;
    router: Pick<PageRouting, 'parseRoute' | 'getDefaultRoute'> & { ensureInitialized(): void };
    auth: RouterDependencies['auth'];
    navigationMiddleware: NavigationMiddlewareController;
    componentLoader: RouterComponentLoader;
    lifecycle: ReturnType<typeof createRouterLifecycleDependencies>;
    sectionTracker: { initialize(): void };
    sidebarTargets: SidebarComponentTargets;
    getSidebarService: RouterDependencies['getSidebarService'];
}

const executeRoutePaneNavigation = async (dependencies: RouteExecutionDependencies, request: NavigationRequest, signal: AbortSignal): Promise<void> => {
    let pane = dependencies.pane;
    let placement: PagePaneAdmissionResult | null = null;
    const focusIntent = pane.getNavigationFocusIntent(signal);
    const authEpoch = dependencies.auth.authEpoch;
    const repairHistory = (): void => {
        const focused = dependencies.pagePanes.getFocusedPane();
        const route = focused?.currentRoute;
        const parsed = route ? dependencies.router.parseRoute(route) : null;
        if (focused && route) dependencies.browserNavigation.project(route, focused.id, 'replace', focusIntent, { title: parsed ? resolveRouteTitle(parsed.route) : '' });
    };
    try {
        await executeNavigationRequest(
            {
                admitPlacement: async (context) => {
                    const admitted = await dependencies.pagePanes.navigation.admit(pane, context);
                    pane = admitted.pane;
                    placement = admitted;
                    return {
                        ...admitted,
                        complete: () => {
                            admitted.complete?.();
                            if (admitted.type === 'retained' && pane.presentation.isFocused() && pane.currentRoute) dependencies.browserNavigation.project(pane.currentRoute, pane.id, 'replace', focusIntent, { title: resolveRouteTitle(context.route) });
                            else if (!request.pushState && !pane.presentation.isFocused()) repairHistory();
                        }
                    };
                },
                authEpoch,
                router: { parseRoute: (path: string) => dependencies.router.parseRoute(path), getDefaultRoute: () => dependencies.router.getDefaultRoute() },
                state: {
                    get presentation() {
                        return pane.presentation;
                    },
                    get currentMountScope() {
                        return pane.outlet.getPageHost().getCurrentMountScope();
                    },
                    get currentRoute() {
                        return pane.currentRoute;
                    },
                    setCurrentRoute: (route: string | null) => {
                        pane.currentRoute = route;
                    },
                    setLastNavigationDetail: () => {}
                },
                parseRoute: (path: string) => dependencies.router.parseRoute(path),
                resolveRouteDetails: (path: string, route: RouteDefinition | null, parameters: RouteParameters | null) =>
                    resolveRouteDetails({
                        ensureInitialized: () => dependencies.router.ensureInitialized(),
                        path,
                        route,
                        parameters,
                        parseRoute: (targetPath: string) => dependencies.router.parseRoute(targetPath)
                    }),
                validateNavigation: (route: RouteDefinition) => {
                    if (!route.component) {
                        throw new Error('Route missing component');
                    }
                },
                runNavigationMiddleware: async (context: NavigationContext) => dependencies.navigationMiddleware.run(context),
                preloadDependencies: async (route: RouteDefinition) => dependencies.componentLoader.preloadDependencies(route, signal),
                get pageOutlet() {
                    return pane.outlet;
                },
                redirect: async (target: string, options: NavigationOptions) => {
                    await executeRoutePaneNavigation({ ...dependencies, pane }, normalizeNavigationRequest(target, { intent: request.intent, presentation: request.presentation, ...options, force: true }), signal);
                },
                lifecycle: { ...dependencies.lifecycle, navigationPresentation: () => ({ paneId: pane.id, mountGeneration: pane.outlet.getPageHost().getCurrentMountScope()?.generation ?? null, focused: pane.presentation.isFocused() }) },
                sectionTracker: dependencies.sectionTracker,
                loadPageComponent: async (componentName: string, parameters: RouteParameters, renderOptions: RouterPageRenderOptions): Promise<boolean> => {
                    const rendered = await pane.outlet.render({
                        component: componentName,
                        createMountScope: (binding) =>
                            createPageMountScope({
                                type: 'pane',
                                ownerId: pane.id,
                                candidateRoute: renderOptions.routePath,
                                authEpoch,
                                readAuthEpoch: () => dependencies.auth.authEpoch,
                                binding,
                                routing: pane.routing,
                                presentation: pane.presentation
                            }),
                        parameters,
                        ...renderOptions,
                        mountPublication: {
                            commit: () => {
                                placement?.publication.commit();
                                renderOptions.mountPublication.commit();
                                if (!pane.setNavigationCommitted(signal, true)) throw createAbortError('Navigation lost its native commit owner');
                            },
                            rollback: () => {
                                pane.setNavigationCommitted(signal, false);
                                renderOptions.mountPublication.rollback();
                                placement?.publication.rollback();
                            }
                        },
                        afterCommit: async (previousContainer) => {
                            dependencies.pagePanes.persistence.changed();
                            const retirement = await placement?.afterCommit();
                            if (retirement) reportPagePaneRetirementOutcome(retirement);
                            if (pane.presentation.isFocused()) runCommittedNavigationCleanup(previousContainer);
                            await renderOptions.afterCommit(previousContainer);
                        },
                        finalAdmission: () => {
                            throwIfAborted(signal);
                            if (authEpoch !== dependencies.auth.authEpoch) throw createAbortError('Authentication changed during page preparation');
                            renderOptions.finalAdmission?.();
                        },
                        commitNavigation: pane.localization.commitRendered(() => {
                            if (authEpoch !== dependencies.auth.authEpoch) return;
                            const container = pane.outlet.getContainer();
                            container.inert = false;
                            container.classList.remove('u-hidden');
                            placement?.present();
                            renderOptions.commitNavigation();
                        })
                    });
                    return rendered !== null;
                },
                sidebarTargets: dependencies.sidebarTargets,
                resolveSidebarService: () => resolveSidebarService(dependencies.getSidebarService, isSidebarServiceContract),
                projectHistory: (route, title, mode) => {
                    dependencies.browserNavigation.project(route, pane.id, placement?.historyMode === 'replace' ? 'replace' : mode, focusIntent, { title });
                },
                repairHistory,
                resolveRouteTitle,
                connectionHold: {
                    acquire: acquireNavigationConnectionHold,
                    release: releaseNavigationConnectionHold
                }
            },
            request,
            signal
        );
    } catch (error) {
        if (!request.pushState) repairHistory();
        throw error;
    }
};

export { executeRoutePaneNavigation };
export type { RouteExecutionDependencies };
