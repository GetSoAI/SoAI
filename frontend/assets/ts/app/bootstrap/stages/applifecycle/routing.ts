/* SoAI - Frontend application routing [frontend/assets/ts/app/bootstrap/stages/applifecycle/routing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requirePageHostApi } from '@app/bootstrap/stages/pageHost.ts';
import type { LifecycleRoute, RouteKey } from '@app/bootstrap/stages/applifecycle/types.ts';
import type { WizardStatus } from '@core/auth/public.ts';
import { isFreshInstallWizardStatus } from '@core/auth/wizardStatus.ts';
import { getLocation } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
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
    toggleMainUI: (show: boolean) => void;
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
    router: Router;
}

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

export const resolveInitialRoute = async ({ isAuthenticated, needsWizard, router, toggleMainUI, isWizardCompletionPending }: ResolveInitialRouteOptions): Promise<RouteKey> => {
    toggleMainUI(isAuthenticated);
    const hash = getLocation().hash.slice(1);

    if (!isAuthenticated) {
        if (hash) {
            let parsed: ReturnType<Router['parseRoute']> = null;
            try {
                parsed = router.parseRoute(hash);
            } catch (error) {
                ensureError(error);
                parsed = null;
            }
            if (parsed) {
                const routeObject = parsed.route;
                const auth = routeObject.auth;
                if (auth !== true) {
                    const component = routeObject.component;
                    if (isString(component) && component) {
                        if (component === AUTH_ROUTE_WIZARD) {
                            return hash;
                        }
                        if (!needsWizard) {
                            return hash;
                        }
                    }
                }
            }
        }
        return needsWizard ? AUTH_ROUTE_WIZARD : AUTH_ROUTE_LOGIN;
    }

    if (isWizardCompletionPending()) {
        return AUTH_ROUTE_WIZARD;
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

    await host.whenReady({ waitForReveal: false });
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
