/* SoAI - Router route matching and navigation presentation [frontend/assets/ts/core/routing/router/navigation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { RouteDefinition, RouteMatcher, RouteParameters } from '@core/routing/router/types.ts';
import { isString } from '@core/typeGuards.ts';

function resolveRouteTitle(route: RouteDefinition): string;
function resolveRouteTitle(route: null): null;
function resolveRouteTitle(route: RouteDefinition | null): string | null;
function resolveRouteTitle(route: RouteDefinition | null): string | null {
    if (!route) return null;
    const title = route.getTitle();
    return title && title.trim() ? title : i18n.t('common.unknown');
}

const parseQueryParameters = (queryString: string | undefined): RouteParameters => (queryString ? Object.fromEntries(new URLSearchParams(queryString)) : {});

const compileDynamicMatcher = (path: string): RouteMatcher | null => {
    if (!isString(path) || !path.includes(':')) return null;
    const parameterNames: string[] = [];
    const pattern = path.replace(/:([^/]+)/g, (_match: string, name: string) => {
        parameterNames.push(name);
        return '([^/]+)';
    });
    return { regex: new RegExp(`^${pattern}$`), parameterNames };
};

export { compileDynamicMatcher, parseQueryParameters, resolveRouteTitle };
