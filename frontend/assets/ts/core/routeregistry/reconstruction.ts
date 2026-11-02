/* SoAI - Route reconstruction and consumed initial query policy [frontend/assets/ts/core/routeregistry/reconstruction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasOwn } from '@core/typeGuards.ts';
import type { RouteDefinition, RouteReconstruction } from '@core/routeregistry/contracts.ts';
import type { PageRouting } from '@core/routing/router/types.ts';
import { buildRouteWithoutQueryParameters, getQueryParametersFromHash } from '@core/routing/router/queryParameters.ts';

const INITIAL_MODAL_QUERY_KEYS: readonly string[] = Object.freeze(['modal']);
const AUTOMATION_RUN_QUERY_KEY = 'run_id';
const AUTOMATION_RECONSTRUCTION_QUERY_KEYS: readonly string[] = Object.freeze([...INITIAL_MODAL_QUERY_KEYS, AUTOMATION_RUN_QUERY_KEY]);
const PLUGINS_INITIAL_MODAL_QUERY_KEYS: readonly string[] = Object.freeze(['modal', 'plugin']);
const MODELS_INITIAL_ACTION_QUERY_KEYS: readonly string[] = Object.freeze(['action', 'plugin', 'vm', 'search']);
const READ_ROUTE_RECONSTRUCTION: RouteReconstruction = Object.freeze({ discardQuery: Object.freeze([]) });
const CLEAN_READ_ROUTE_RECONSTRUCTION: RouteReconstruction = Object.freeze({ ...READ_ROUTE_RECONSTRUCTION, parking: 'clean' });

const projectReconstructionRoute = (path: string, definition: RouteDefinition): string | null => {
    const policy = definition.reconstruction;
    if (!policy || !definition.auth || definition.layout.exclusive) return null;
    const query = getQueryParametersFromHash(`#${path}`);
    if ((policy.whenQuery && !hasOwn(query, policy.whenQuery)) || !policy.discardQuery.some((key) => hasOwn(query, key))) return path;
    return buildRouteWithoutQueryParameters(path, query, policy.discardQuery);
};

const consumeRouteQuery = (router: Pick<PageRouting, 'getCurrentRoute' | 'getQueryParameters' | 'replaceCurrentRoute'>, keys: readonly string[]): void => {
    const route = router.getCurrentRoute();
    if (!route) throw new Error('Initial query consumption requires its mounted route');
    const query = router.getQueryParameters();
    if (!keys.some((key) => hasOwn(query, key))) return;
    router.replaceCurrentRoute(buildRouteWithoutQueryParameters(route, query, keys));
};

export { INITIAL_MODAL_QUERY_KEYS, AUTOMATION_RUN_QUERY_KEY, AUTOMATION_RECONSTRUCTION_QUERY_KEYS, PLUGINS_INITIAL_MODAL_QUERY_KEYS, MODELS_INITIAL_ACTION_QUERY_KEYS, READ_ROUTE_RECONSTRUCTION, CLEAN_READ_ROUTE_RECONSTRUCTION, projectReconstructionRoute, consumeRouteQuery };
