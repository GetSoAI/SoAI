/* SoAI - Shared routing router actions [frontend/assets/ts/core/routing/router/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { coerceErrorMessage } from '@core/errors/coerce.ts';
import { compileDynamicMatcher, parseQueryParameters } from '@core/routing/router/navigation.ts';
import { normalizeNavigationMeta } from '@core/routing/router/navigationRequest.ts';
import { isNavigationRequest, isRouteDefinition, isRouteParameters } from '@core/routing/router/routerTypeGuards.ts';
import type { PageOutletService } from '@core/routing/router/routerDependencies.ts';
import type { NavigationContext, NavigationRequest, NavigationRouterHost, RouteDefinition, RouteEntry, RouteParameters } from '@core/routing/router/types.ts';
import { hasFunctionProperty, hasOwn, isObject, isString } from '@core/typeGuards.ts';
import type { PageInstance } from '@core/pagehost/types.ts';
import type { PageHostInstance } from '@core/pageoutlet/types.ts';

interface PageHostWithGetCurrent {
    getCurrent: PageHostInstance['getCurrent'];
}

interface NavigationRouteReferenceCandidate {
    path?: string | undefined;
    route?: RouteDefinition | null | undefined;
    parameters?: RouteParameters | null | undefined;
}

interface NavigationContextCandidate {
    request?: NavigationRequest | null | undefined;
    route?: RouteDefinition | null | undefined;
    parameters?: RouteParameters | null | undefined;
    meta?: NavigationContext['meta'] | null | undefined;
    from?: NavigationRouteReferenceCandidate | null | undefined;
    router?: NavigationRouterHost | null | undefined;
    startedAt?: number | null | undefined;
    signal?: AbortSignal | null | undefined;
}

const isPageHostWithGetCurrent = (candidate: PageHostInstance | PageHostWithGetCurrent | null | undefined): candidate is PageHostWithGetCurrent => {
    if (!isObject(candidate)) {
        return false;
    }
    return hasFunctionProperty(candidate, 'getCurrent');
};

const hasCurrentPageEntry = (value: { name: string; instance: PageInstance } | null): boolean => value !== null;

const registerRouteDefinitions = (routeDefinitions: RouteDefinition[], routes: Map<string, RouteEntry>, dynamicRoutes: RouteEntry[]): void => {
    if (!Array.isArray(routeDefinitions) || routeDefinitions.length === 0) {
        throw new Error('Router requires route definitions');
    }

    routes.clear();
    dynamicRoutes.length = 0;
    for (const definition of routeDefinitions) {
        const path = toTrimmedString(definition.path);
        if (!path) {
            throw new Error('Route definitions must include a non-empty path');
        }
        const entry: RouteEntry = {
            ...definition,
            path,
            matcher: compileDynamicMatcher(path)
        };
        if (entry.matcher) {
            dynamicRoutes.push(entry);
        }
        routes.set(path, entry);
    }
};

const parseRoutePath = (routePath: string, routes: Map<string, RouteEntry>, dynamicRoutes: RouteEntry[]): { route: RouteEntry; parameters: RouteParameters } | null => {
    const trimmed = toTrimmedString(routePath);
    if (!trimmed) {
        throw new Error('Router.parseRoute requires a non-empty route path');
    }

    const normalized = trimmed.startsWith('/') ? trimmed.slice(1) : trimmed;
    const queryStart = normalized.indexOf('?');
    const basePath = queryStart < 0 ? normalized : normalized.slice(0, queryStart);
    const queryString = queryStart < 0 ? undefined : normalized.slice(queryStart + 1);
    const queryParameters = parseQueryParameters(queryString);

    if (!basePath) {
        return null;
    }
    const staticRoute = routes.get(basePath) || null;
    if (staticRoute) {
        return { route: staticRoute, parameters: queryParameters };
    }

    for (const entry of dynamicRoutes) {
        if (!entry.matcher) {
            continue;
        }
        const match = entry.matcher.regex.exec(basePath);
        if (!match) {
            continue;
        }
        const pathParameters: RouteParameters = {};
        for (let index = 0; index < entry.matcher.parameterNames.length; index += 1) {
            const name = entry.matcher.parameterNames[index];
            if (!name) {
                continue;
            }
            const value = match[index + 1] ?? '';
            try {
                pathParameters[name] = decodeURIComponent(value);
            } catch (error) {
                const reason = coerceErrorMessage(error);
                throw new Error(`Failed to decode route param '${name}' for path '${basePath}': ${reason}`);
            }
        }
        return { route: entry, parameters: { ...queryParameters, ...pathParameters } };
    }

    throw new Error(`No route found for path: ${normalized}`);
};

const getRouteFromHash = (hash: string): string | null => {
    if (!isString(hash)) {
        throw new Error('Location hash must be a string');
    }
    return hash.length > 1 ? hash.slice(1) : null;
};

const ensurePageHost = (pageOutlet: PageOutletService): PageHostWithGetCurrent | null => {
    const host = pageOutlet.getPageHost();
    return isPageHostWithGetCurrent(host) ? host : null;
};

const shouldSkipNavigation = (currentRoute: string | null, targetPath: string, pageOutlet: PageOutletService): boolean => {
    if (currentRoute !== targetPath) {
        return false;
    }
    const outletState = typeof pageOutlet.getState === 'function' ? pageOutlet.getState() : null;
    const hostCandidate = pageOutlet.getPageHost();
    const hasCurrent = isPageHostWithGetCurrent(hostCandidate) && hasCurrentPageEntry(hostCandidate.getCurrent());
    return outletState === 'ready' && hasCurrent;
};

const resolveRouteDetails = (options: { ensureInitialized: () => void; path: string; route: RouteDefinition | null; parameters: RouteParameters | null; parseRoute: (path: string) => { route: RouteEntry; parameters: RouteParameters } | null }): { path: string; route: RouteDefinition; parameters: RouteParameters } => {
    options.ensureInitialized();
    const targetPath = toTrimmedString(options.path);
    if (!targetPath) {
        throw new Error('Router requires a path');
    }
    const routeInfo = options.parseRoute(targetPath);
    if (!routeInfo) {
        throw new Error(`No route found for path: ${targetPath}`);
    }
    return {
        path: targetPath,
        route: options.route ?? routeInfo.route,
        parameters: options.parameters ?? routeInfo.parameters
    };
};

const isNavigationRouterHost = (value: NavigationRouterHost | null | undefined): value is NavigationRouterHost => isObject(value) && hasFunctionProperty(value, 'parseRoute') && hasFunctionProperty(value, 'getDefaultRoute');

const createNavigationContext = (options: { router: NavigationRouterHost | null; currentRoute: string | null; parseRoute: (path: string) => { route: RouteEntry; parameters: RouteParameters } | null; request: NavigationRequest; route: RouteDefinition; parameters: RouteParameters; signal: AbortSignal }): NavigationContext => {
    if (!isNavigationRequest(options.request)) {
        throw new TypeError('request must be a navigation request');
    }
    const parsed = options.currentRoute ? options.parseRoute(options.currentRoute) : null;
    const from = parsed && options.currentRoute ? { path: options.currentRoute, route: parsed.route, parameters: parsed.parameters } : null;
    return {
        router: options.router,
        request: options.request,
        route: options.route,
        parameters: options.parameters,
        meta: options.request.meta ? { ...options.request.meta } : {},
        from,
        startedAt: Date.now(),
        signal: options.signal
    };
};

const requireNavigationContext = (value: NavigationContextCandidate | null | undefined): NavigationContext => {
    if (!isObject(value)) {
        throw new Error('Navigation middleware context must be an object');
    }

    const requestValue = 'request' in value ? value.request : null;
    if (!requestValue || !isNavigationRequest(requestValue)) {
        throw new Error('Navigation context missing request');
    }

    const routeValue = 'route' in value ? value.route : null;
    if (!routeValue || !isRouteDefinition(routeValue)) {
        throw new Error('Navigation context missing route');
    }

    const parametersValue = 'parameters' in value ? value.parameters : null;
    if (!parametersValue || !isRouteParameters(parametersValue)) {
        throw new Error('Navigation context missing params');
    }

    const metaValue = 'meta' in value ? value.meta : null;
    const meta = isObject(metaValue) ? normalizeNavigationMeta(metaValue) : {};

    const startedAtValue = 'startedAt' in value ? value.startedAt : null;
    const startedAt = typeof startedAtValue === 'number' && Number.isFinite(startedAtValue) ? startedAtValue : Date.now();
    const signal = 'signal' in value ? value.signal : null;
    if (!(signal instanceof AbortSignal)) {
        throw new Error('Navigation context missing cancellation signal');
    }

    const fromValue = 'from' in value ? value.from : null;
    let from: NavigationContext['from'] = null;
    if (isObject(fromValue)) {
        const fromPath = 'path' in fromValue ? fromValue.path : null;
        const fromRoute = 'route' in fromValue ? fromValue.route : null;
        const fromParameters = 'parameters' in fromValue ? fromValue.parameters : null;
        if (isString(fromPath) && fromRoute && isRouteDefinition(fromRoute) && fromParameters && isRouteParameters(fromParameters)) {
            from = { path: fromPath, route: fromRoute, parameters: fromParameters };
        }
    }

    const routerValue = hasOwn(value, 'router') ? value.router : null;
    return {
        router: isNavigationRouterHost(routerValue) ? routerValue : null,
        request: requestValue,
        route: routeValue,
        parameters: parametersValue,
        meta,
        from,
        startedAt,
        signal
    };
};

export { createNavigationContext, ensurePageHost, getRouteFromHash, parseRoutePath, registerRouteDefinitions, requireNavigationContext, resolveRouteDetails, shouldSkipNavigation };
