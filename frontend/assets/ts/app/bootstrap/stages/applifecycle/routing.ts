/* SoAI - Frontend application routing [frontend/assets/ts/app/bootstrap/stages/applifecycle/routing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requirePageHostApi } from '@app/bootstrap/stages/pageHost.ts';
import type { LifecycleRoute, RouteKey } from '@app/bootstrap/stages/applifecycle/types.ts';
import type { WizardStatus } from '@core/auth/public.ts';
import { isFreshInstallWizardStatus } from '@core/auth/wizardStatus.ts';
import { getLocation } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { LifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { isAiSetupResumeRequest } from '@core/routing/router/aiSetupRoutes.ts';
import { AUTH_ROUTE_LOGIN, AUTH_ROUTE_WIZARD, resolveAuthenticatedRouteTarget } from '@core/routing/router/authRouteTarget.ts';
import type { PageInstance } from '@core/pagehost/types.ts';
import type { NavigationDetail } from '@core/routing/router/types.ts';
import type { Router } from '@core/routing/router/Router.ts';
import { isInstanceOf, isNullOrUndefined, isObject, isString } from '@core/typeGuards.ts';
import type { ChartModulesAccess } from '@features/charts/chartModules.ts';

interface ResolveInitialRouteOptions {
    isAuthenticated: boolean;
    needsWizard: boolean;
    router: Router;
    isWizardCompletionPending: () => boolean;
}

interface WarmupChartsOptions {
    route: LifecycleRoute;
    chartWarmupRoutes: Set<string>;
    chartModules: ChartModulesAccess;
    currentWarmupPromise: Promise<void> | null;
    setWarmupPromise: (promise: Promise<void> | null) => void;
}

interface EnsureRouteRenderedOptions {
    route: LifecycleRoute;
    router: Pick<Router, 'contentContainer' | 'getCurrentRoute' | 'getRouteFromHash' | 'getPageOutlet'>;
}

type BootstrapRouteRouter = EnsureRouteRenderedOptions['router'] & Pick<Router, 'initialized' | 'getLatestNavigationCompletion'>;

interface RenderedPageState {
    instance?:
        | (PageInstance & {
              isInitialized?: boolean;
          })
        | null;
}

export const resolveNavigationRoute = (detail: NavigationDetail | null): LifecycleRoute => {
    if (!isObject(detail)) {
        return null;
    }
    const resolved = detail['resolvedRoute'];
    const component = detail['component'];
    const route = detail['route'];
    if (!isNullOrUndefined(resolved)) {
        return resolved;
    }
    if (!isNullOrUndefined(component)) {
        return component;
    }
    if (!isNullOrUndefined(route)) {
        return route;
    }
    return null;
};

export const resolveRouteKey = (route: LifecycleRoute | undefined): string | null => {
    if (!route) {
        return null;
    }
    if (isString(route)) {
        return route;
    }
    if (!isObject(route)) {
        return null;
    }
    const component = route['component'];
    if (isString(component) && component) {
        return component;
    }
    const path = route['path'];
    if (isString(path) && path) {
        return path;
    }
    return null;
};

const parseHashRoute = (router: Router, hash: string): ReturnType<Router['parseRoute']> => {
    if (!hash) return null;
    try {
        return router.parseRoute(hash);
    } catch (error) {
        errorHandler.warn('AppLifecycle', 'Ignoring an unparseable initial route', ensureError(error));
        return null;
    }
};

export const resolveInitialRoute = ({ isAuthenticated, needsWizard, router, isWizardCompletionPending }: ResolveInitialRouteOptions): RouteKey => {
    const hash = getLocation().hash.slice(1);
    const parsed = parseHashRoute(router, hash);

    if (!isAuthenticated) {
        if (parsed?.route.auth === true && !needsWizard) return hash;
        if (parsed && parsed.route.auth !== true) {
            const component = parsed.route.component;
            if (isString(component) && component && (component === AUTH_ROUTE_WIZARD || !needsWizard)) {
                return hash;
            }
        }
        return needsWizard ? AUTH_ROUTE_WIZARD : AUTH_ROUTE_LOGIN;
    }

    if (isWizardCompletionPending()) {
        return AUTH_ROUTE_WIZARD;
    }

    if (parsed?.route.component === AUTH_ROUTE_WIZARD && isAiSetupResumeRequest(parsed.parameters)) {
        return hash;
    }

    return resolveAuthenticatedRouteTarget(router, { currentRoute: hash });
};

export const resolveLoggedOutRoute = (wizardStatus: WizardStatus | null): RouteKey => {
    return isFreshInstallWizardStatus(wizardStatus) ? AUTH_ROUTE_WIZARD : AUTH_ROUTE_LOGIN;
};

export const warmupCharts = ({ route, chartWarmupRoutes, chartModules, currentWarmupPromise, setWarmupPromise }: WarmupChartsOptions): Promise<void> | undefined => {
    const key = resolveRouteKey(route);
    if (!key || !chartWarmupRoutes.has(key)) {
        return;
    }
    if (currentWarmupPromise) {
        return currentWarmupPromise;
    }

    const task = chartModules.ensure().then(() => undefined);
    setWarmupPromise(task);
    return task.finally(() => {
        setWarmupPromise(null);
    });
};

export const ensureRouteRendered = async ({ route, router }: EnsureRouteRenderedOptions): Promise<void> => {
    const container = router.contentContainer;
    if (!isInstanceOf(container, HTMLElement)) {
        throw new Error('Router must maintain a valid content container');
    }

    const routeKey = resolveRouteKey(route) || router.getCurrentRoute() || router.getRouteFromHash();
    if (!routeKey) {
        throw new Error('Unable to resolve route key for rendering verification');
    }

    const outlet = router.getPageOutlet();
    const host = requirePageHostApi(outlet.getPageHost(), routeKey);

    await host.whenReady();
    const stateCandidate = host.getCurrent();
    const hasState = stateCandidate !== undefined && stateCandidate !== null;
    const stateObject: RenderedPageState | null = hasState && isObject(stateCandidate) ? stateCandidate : null;
    const instanceCandidate = stateObject?.instance ?? null;
    if (instanceCandidate?.isInitialized === true) {
        return;
    }

    errorHandler.warn('AppLifecycle', `Route rendering verification failed: ${routeKey}`);
    throw new Error(i18n.t('app.errors.routeNotReady'));
};

export const ensureBootstrapRouteRendered = async (router: BootstrapRouteRouter): Promise<string> => {
    while (true) {
        const completion = router.getLatestNavigationCompletion();
        if (!completion || !router.initialized) throw new LifecycleCancellationError('Bootstrap navigation is no longer available', 'router-destroyed');
        let navigationFailure: Error | null = null;
        try {
            await completion;
        } catch (error) {
            navigationFailure = ensureError(error);
        }
        if (completion !== router.getLatestNavigationCompletion()) continue;
        if (navigationFailure && router.getPageOutlet().getState?.() !== 'ready') throw navigationFailure;
        try {
            await ensureRouteRendered({ route: router.getCurrentRoute(), router });
        } catch (error) {
            if (completion !== router.getLatestNavigationCompletion()) continue;
            throw navigationFailure ?? error;
        }
        if (completion !== router.getLatestNavigationCompletion()) continue;
        const route = router.getCurrentRoute();
        if (!route) throw new Error('Bootstrap navigation completed without an active route');
        return route;
    }
};
