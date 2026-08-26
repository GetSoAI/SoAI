/* SoAI - Shared routing router events [frontend/assets/ts/core/routing/router/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readErrorMessage } from '@core/routing/router/navigationMiddlewareNormalization.ts';
import { DEFAULT_AUTHENTICATED_ROUTE } from '@core/routing/router/authRouteTarget.ts';
import type { ErrorHandlerService, ResourceTrackerInstance } from '@core/routing/router/routerDependencies.ts';
import type { NavigationOptions, RouteEntry, RouteParameters } from '@core/routing/router/types.ts';
import { isRecordLike } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { claimErrorReporting } from '@core/errors/reportingOwnership.ts';
import { notifyHandledOperationError } from '@core/operationErrorNotifier.ts';

interface RouterInitializationEventsDependencies {
    resources: ResourceTrackerInstance;
    getWindow: () => Window;
    getRouteFromHash: () => string | null;
    parseRoute: (target: string) => { route: RouteEntry; parameters: RouteParameters } | null;
    navigate: (target: string, options: NavigationOptions) => Promise<void>;
    errorHandler: ErrorHandlerService;
    renderCriticalError: (message: string) => void;
    isInitialized: () => boolean;
    getCurrentRoute: () => string | null;
}

const normalizeRouteOrDefault = (dependencies: { parseRoute: (target: string) => { route: RouteEntry; parameters: RouteParameters } | null; errorHandler: ErrorHandlerService }, route: string): string => {
    try {
        const parsed = dependencies.parseRoute(route);
        if (parsed) {
            return route;
        }
    } catch (error) {
        dependencies.errorHandler.warn('Router', 'Unknown route on hashchange; redirecting to default route', ensureError(error));
        return DEFAULT_AUTHENTICATED_ROUTE;
    }
    dependencies.errorHandler.warn('Router', 'Unresolved route on hashchange; redirecting to default route');
    return DEFAULT_AUTHENTICATED_ROUTE;
};

const reportNavigationEventFailure = (dependencies: RouterInitializationEventsDependencies, message: string, error: Error): void => {
    if (!claimErrorReporting(error)) {
        return;
    }
    notifyHandledOperationError(error);
    dependencies.errorHandler.error('Router', message, error);
};

const registerRouterInitializationEvents = (dependencies: RouterInitializationEventsDependencies): void => {
    const win = dependencies.getWindow();

    dependencies.resources.addEventListener(win, 'hashchange', async () => {
        const route = dependencies.getRouteFromHash();
        if (!route) {
            return;
        }
        const targetRoute = normalizeRouteOrDefault(
            {
                parseRoute: dependencies.parseRoute,
                errorHandler: dependencies.errorHandler
            },
            route
        );
        try {
            if (targetRoute === route) {
                await dependencies.navigate(route, { pushState: false });
                return;
            }
            await dependencies.navigate(targetRoute, { replace: true, force: true });
        } catch (error) {
            const runtimeError = ensureError(error);
            reportNavigationEventFailure(dependencies, 'Navigation failed on hashchange', runtimeError);
        }
    });

    dependencies.resources.addEventListener(win, 'unhandledrejection', (event: Event) => {
        try {
            const promiseRejectionCtor: typeof PromiseRejectionEvent | null = typeof PromiseRejectionEvent === 'function' ? PromiseRejectionEvent : null;
            const reason = promiseRejectionCtor && event instanceof promiseRejectionCtor ? event.reason : isRecordLike(event) && 'reason' in event ? event.reason : null;
            const message = readErrorMessage(reason);
            if (message && message.includes('navigation')) {
                event.preventDefault();
                dependencies.renderCriticalError('Navigation system error. Please refresh the page.');
            }
        } catch (handlerError) {
            const runtimeError = ensureError(handlerError);
            dependencies.errorHandler.error('Router', 'Unhandled rejection handler failed', runtimeError);
        }
    });

    dependencies.resources.addEventListener(win, 'soai:language:changed', () => {
        const currentRoute = dependencies.getCurrentRoute();
        if (!currentRoute || !dependencies.isInitialized()) {
            return;
        }
        dependencies.navigate(currentRoute, { pushState: false, force: true }).catch((error) => {
            const runtimeError = ensureError(error);
            reportNavigationEventFailure(dependencies, 'Navigation failed on language change', runtimeError);
        });
    });
};

const buildQueryRoute = (path: string, queryParameters: Record<string, string> = {}): string => {
    const queryString = new URLSearchParams(queryParameters).toString();
    return queryString ? `${path}?${queryString}` : path;
};

const buildRouteWithoutQueryParameters = (path: string, queryParameters: Record<string, string>, excludedKeys: readonly string[]): string => {
    const excluded = new Set(excludedKeys);
    const nextParameters = new URLSearchParams();
    for (const [key, value] of Object.entries(queryParameters)) {
        if (!excluded.has(key)) {
            nextParameters.append(key, value);
        }
    }
    const queryString = nextParameters.toString();
    return queryString ? `${path}?${queryString}` : path;
};

const getQueryParametersFromHash = (hash: string): Record<string, string> => {
    const queryStart = hash.indexOf('?');
    const queryString = queryStart < 0 ? '' : hash.slice(queryStart + 1);
    return queryString ? Object.fromEntries(new URLSearchParams(queryString)) : {};
};

export { buildQueryRoute, buildRouteWithoutQueryParameters, getQueryParametersFromHash, registerRouterInitializationEvents };
