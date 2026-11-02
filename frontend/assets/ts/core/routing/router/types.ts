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
    intent?: 'navigate' | 'select' | 'split' | 'restore' | 'close' | undefined;
    presentation?: 'user' | 'background' | undefined;
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
    admitPlacement: (context: NavigationContext) => Promise<NavigationPlacementAdmission>;
    approveDestruction?: ((approval: NavigationProtectionApproval) => void) | undefined;
    readonly destructionOwner: PageMountScope | null;
    router: NavigationRouterHost | null;
    request: NavigationRequest;
    route: RouteDefinition;
    parameters: RouteParameters;
    meta: JsonObject;
    from: { path: string; route: RouteDefinition; parameters: RouteParameters } | null;
    startedAt: number;
    signal: AbortSignal;
}

interface NavigationPlacementAdmission {
    readonly type: 'retained' | 'render' | 'close';
    readonly close?: ((publish: () => void) => Promise<void>) | undefined;
    readonly prepareClose?: (() => Promise<() => void>) | undefined;
    readonly guardContexts: readonly NavigationContext[];
    readonly guardPhase?: 'before-prepare' | 'before-commit' | undefined;
    readonly evaluateGuards?: (() => Promise<NavigationResultType | null>) | undefined;
    readonly finalAdmission?: (() => void) | undefined;
    readonly complete?: (() => void) | undefined;
    readonly settle?: (() => void) | undefined;
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
    intent?: NavigationRequest['intent'];
    presentation?: NavigationRequest['presentation'];
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

export type { RouteMatcher, RouteEntry, RouteParameters, QueryScalar, QueryValue, QueryParameterValue, QueryParameters, SoaiOsAccessState, SoaiOsCapabilitiesSnapshot, NavigationRequest, NavigationRouterHost, NavigationContext, NavigationPlacementAdmission, NavigationDetail, NavigationOptions, NavigationTarget, MiddlewareOutcome, MiddlewareNext, Middleware, RouteDefinition, SidebarComponentTargets, RouteData };

export interface PageMountPresentation {
    isVisible(): boolean;
    isFocused(): boolean;
    subscribe(listener: () => void): () => void;
}

export interface PageMountBinding {
    readonly generation: symbol;
    isCurrent(): boolean;
    isActive(): boolean;
    isCommitted(): boolean;
    subscribe(listener: () => void): () => void;
}

export interface PageMountScope {
    readonly type: 'pane' | 'standalone';
    readonly ownerId: string;
    readonly generation: symbol;
    readonly candidateRoute: string;
    readonly authEpoch: number;
    readonly routing: PageRouting;
    readonly presentation: PageMountPresentation;
    readonly admission: {
        isCurrent(): boolean;
        isActive(): boolean;
        canMutate(): boolean;
        blockMutations(): () => void;
        requireActive(): void;
    };
}

export type PageMountScopeFactory = (binding: PageMountBinding) => PageMountScope;

export interface GlobalPresentationOwner {
    readonly type: 'global';
    readonly ownerId: string;
    readonly generation: symbol;
}

export type PresentationOwner = PageMountScope | GlobalPresentationOwner;

export interface PageRouting {
    back(): void;
    navigate(target: string | NavigationTarget, options?: NavigationOptions): Promise<void>;
    navigateWithQuery(path: string, queryParameters?: Record<string, string>, options?: NavigationOptions): void;
    reload(): Promise<void>;
    getCurrentRoute(): string | null;
    getRouteParameters(): RouteParameters;
    getQueryParameters(): RouteParameters;
    replaceCurrentRoute(target: string | NavigationTarget): void;
    parseRoute(path: string): { route: RouteEntry; parameters: RouteParameters } | null;
    getDefaultRoute(): string;
}

interface NavigationResultContinue {
    status: 'continue';
    detail: JsonValue;
}

interface NavigationResultBlocked {
    status: 'blocked';
    reason: string | null;
    failure?: Error | undefined;
}

interface NavigationResultRedirect {
    status: 'redirect';
    target: string;
    options: NavigationOptions;
}

type NavigationResultType = NavigationResultContinue | NavigationResultBlocked | NavigationResultRedirect;

interface NavigationProtectionApproval {
    isCurrent(): boolean;
}

export type { NavigationResultContinue, NavigationResultBlocked, NavigationResultRedirect, NavigationResultType, NavigationProtectionApproval };
