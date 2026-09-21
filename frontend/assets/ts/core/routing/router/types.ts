/* SoAI - Shared frontend routing router public contracts [frontend/assets/ts/core/routing/router/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RouteData, RouteDefinition, SidebarComponentTargets } from '@core/routeregistry/contracts.ts';
import type { SoaiOsAccessState, SoaiOsCapabilitiesSnapshot } from '@core/soaiOsAccess.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface RouteMatcher {
    regex: RegExp;
    parameterNames: string[];
}

interface RouteEntry extends RouteDefinition {
    matcher: RouteMatcher | null;
}

type RouteParameters = Record<string, string>;

type QueryScalar = string | number | boolean;
type QueryValue = QueryScalar | null | undefined;
type QueryParameterValue = QueryValue | readonly QueryValue[];
type QueryParameters = Record<string, QueryParameterValue>;

interface NavigationRequest {
    path: string;
    pushState: boolean;
    replaceState: boolean;
    force: boolean;
    parameters: RouteParameters | null;
    route: RouteDefinition | null;
    meta: JsonObject | null;
    targetPath?: string;
}

interface NavigationRouterHost {
    parseRoute: (route: string) => { route: RouteEntry; parameters: RouteParameters } | null;
    getDefaultRoute: () => string;
}

interface NavigationContext {
    router: NavigationRouterHost | null;
    request: NavigationRequest;
    route: RouteDefinition;
    parameters: RouteParameters;
    meta: JsonObject;
    from: { path: string; route: RouteDefinition; parameters: RouteParameters } | null;
    startedAt: number;
    signal: AbortSignal;
}

interface NavigationDetail {
    route: string | null;
    component: string | null;
    title: string | null;
    parameters: RouteParameters;
    dataRequirements: RouteData | null;
    phase: string;
    resolvedRoute: RouteDefinition | null;
    resolvedParameters: RouteParameters | null;
    timestamp: number;
    error: JsonObject | null;
}

interface NavigationOptions {
    pushState?: boolean;
    replace?: boolean;
    force?: boolean;
    parameters?: RouteParameters;
    route?: RouteDefinition;
    query?: QueryParameters;
    path?: string;
    meta?: JsonObject;
}

interface NavigationTarget {
    path?: string;
    parameters?: RouteParameters;
    route?: RouteDefinition;
    meta?: JsonObject;
}

interface MiddlewareOutcome {
    status: string;
    detail?: JsonValue;
    reason?: string | null;
    target?: string;
    options?: NavigationOptions;
}

type MiddlewareNext = () => Promise<MiddlewareOutcome>;
type Middleware = (context: NavigationContext, next: MiddlewareNext) => Promise<MiddlewareOutcome>;

export type { RouteMatcher, RouteEntry, RouteParameters, QueryScalar, QueryValue, QueryParameterValue, QueryParameters, SoaiOsAccessState, SoaiOsCapabilitiesSnapshot, NavigationRequest, NavigationRouterHost, NavigationContext, NavigationDetail, NavigationOptions, NavigationTarget, MiddlewareOutcome, MiddlewareNext, Middleware, RouteDefinition, SidebarComponentTargets, RouteData };
