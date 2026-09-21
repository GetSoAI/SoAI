/* SoAI - Shared routing auth route target [frontend/assets/ts/core/routing/router/authRouteTarget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { canAccessUiSurface, createAccessContextFromAuth, createAccessRequirement, type AuthAccessSource } from '@core/access/accessPolicy.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { getRouteRegistry } from '@core/routeregistry/service.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import type { NavigationRouterHost, RouteEntry } from '@core/routing/router/types.ts';

const AUTH_ROUTE_LOGIN = 'login';
const AUTH_ROUTE_WIZARD = 'wizard';
const DEFAULT_AUTHENTICATED_ROUTE = 'dashboard';

const resolveDefaultAuthenticatedRoute = (pageId: string | null, auth: AuthAccessSource): string => {
    const route = pageId === null ? undefined : getRouteRegistry()[pageId];
    if (route?.sidebar?.include !== true) {
        return DEFAULT_AUTHENTICATED_ROUTE;
    }
    const requirement = createAccessRequirement({ authenticated: route.auth, admin: route.adminOnly });
    return canAccessUiSurface(requirement, createAccessContextFromAuth(auth)) ? route.path : DEFAULT_AUTHENTICATED_ROUTE;
};

const isAuthRouteComponent = (component: string): boolean => component === AUTH_ROUTE_LOGIN || component === AUTH_ROUTE_WIZARD;

const normalizeRequestedRoute = (router: NavigationRouterHost, route: string | null | undefined): string | null => {
    if (!isString(route) || !route.trim()) {
        return null;
    }
    const trimmedRoute = route.trim();
    let parsedRoute: { route: RouteEntry; parameters: Record<string, string> } | null = null;
    try {
        parsedRoute = router.parseRoute(trimmedRoute);
    } catch (error) {
        errorHandler.warn('Router', 'Ignoring invalid requested route while resolving authenticated target', ensureError(error));
        return null;
    }
    if (!isObject(parsedRoute)) {
        return null;
    }
    const routeEntry = parsedRoute['route'];
    if (!isObject(routeEntry)) {
        return null;
    }
    return isAuthRouteComponent(routeEntry['component']) ? null : trimmedRoute;
};

const resolveAuthenticatedRouteTarget = (router: NavigationRouterHost, options: { currentRoute?: string | null; redirectAfterLogin?: string | null }): string => {
    const redirectAfterLogin = normalizeRequestedRoute(router, options.redirectAfterLogin);
    if (redirectAfterLogin) {
        return redirectAfterLogin;
    }
    const currentRoute = normalizeRequestedRoute(router, options.currentRoute);
    return currentRoute ?? router.getDefaultRoute();
};

export { AUTH_ROUTE_LOGIN, AUTH_ROUTE_WIZARD, DEFAULT_AUTHENTICATED_ROUTE, isAuthRouteComponent, resolveAuthenticatedRouteTarget, resolveDefaultAuthenticatedRoute };
