/* SoAI - Detached document route ownership without shell history or initialization [frontend/assets/ts/core/routing/router/standaloneRoute.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { buildQueryRoute, getQueryParametersFromHash } from '@core/routing/router/queryParameters.ts';
import { normalizeNavigationRequest } from '@core/routing/router/navigationRequest.ts';
import type { NavigationTarget, PageRouting } from '@core/routing/router/types.ts';

interface StandaloneRouteDependencies {
    component: string;
    initialRoute: string;
    parseRoute: PageRouting['parseRoute'];
    renderRoute: (path: string) => Promise<void>;
    reportFailure: (error: Error) => void;
}

class StandaloneRoute {
    currentRoute: string;
    readonly routing: PageRouting;

    constructor(dependencies: StandaloneRouteDependencies) {
        this.currentRoute = dependencies.initialRoute;
        const resolve = (target: string | NavigationTarget): string => {
            const request = normalizeNavigationRequest(target);
            const route = dependencies.parseRoute(request.path);
            if (!route || route.route.component !== dependencies.component) throw new Error('Detached navigation cannot change page component');
            return request.path;
        };
        this.routing = Object.freeze<PageRouting>({
            back: () => {
                throw new Error('Detached navigation cannot traverse browser history');
            },
            navigate: async (target, options) => {
                const request = normalizeNavigationRequest(target, options);
                await dependencies.renderRoute(resolve(request.path));
            },
            navigateWithQuery: (path, query, options) => {
                void this.routing.navigate(buildQueryRoute(path, query), options).catch((error) => dependencies.reportFailure(ensureError(error)));
            },
            reload: () => dependencies.renderRoute(this.currentRoute),
            getCurrentRoute: () => this.currentRoute,
            getRouteParameters: () => {
                const parsed = dependencies.parseRoute(this.currentRoute);
                if (!parsed) throw new Error(`Detached page cannot parse route: ${this.currentRoute}`);
                return parsed.parameters;
            },
            getQueryParameters: () => getQueryParametersFromHash(`#${this.currentRoute}`),
            replaceCurrentRoute: (target) => {
                this.currentRoute = resolve(target);
            },
            parseRoute: dependencies.parseRoute,
            getDefaultRoute: () => dependencies.initialRoute
        });
    }
}

export { StandaloneRoute };
export type { StandaloneRouteDependencies };
