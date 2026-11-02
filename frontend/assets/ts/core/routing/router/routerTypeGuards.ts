/* SoAI - Shared routing router type guards [frontend/assets/ts/core/routing/router/routerTypeGuards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NavigationRequest, RouteDefinition, RouteParameters } from '@core/routing/router/types.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import { hasFunctionProperty, isBoolean, isNullOrUndefined, isObject, isString } from '@core/typeGuards.ts';

const isRouteDefinition = <T>(value: T): value is T & RouteDefinition => {
    if (!isObject(value)) return false;
    const layout = 'layout' in value ? value.layout : null;
    return 'path' in value && isString(value.path) && Boolean(value.path) && 'component' in value && isString(value.component) && Boolean(value.component) && hasFunctionProperty(value, 'getTitle') && isObject(layout) && 'exclusive' in layout && isBoolean(layout.exclusive) && 'hideSidebar' in layout && isBoolean(layout.hideSidebar) && 'scrollToTopAction' in layout && isBoolean(layout.scrollToTopAction);
};

const isRouteParameters = <T>(value: T): value is T & RouteParameters => {
    if (!isObject(value)) return false;
    for (const entry of Object.values(value)) {
        if (!isString(entry)) return false;
    }
    return true;
};

const isNavigationRequest = <T>(value: T): value is T & NavigationRequest => {
    if (!isObject(value)) return false;
    if ('intent' in value && value.intent !== undefined && value.intent !== 'navigate' && value.intent !== 'select' && value.intent !== 'split' && value.intent !== 'restore' && value.intent !== 'close') return false;
    if ('presentation' in value && value.presentation !== undefined && value.presentation !== 'user' && value.presentation !== 'background') return false;
    const pathValue = 'path' in value ? value.path : null;
    const pushStateValue = 'pushState' in value ? value.pushState : null;
    const replaceStateValue = 'replaceState' in value ? value.replaceState : null;
    const forceValue = 'force' in value ? value.force : null;
    const parametersValue = 'parameters' in value ? value.parameters : null;
    const routeValue = 'route' in value ? value.route : null;
    const metaValue = 'meta' in value ? value.meta : null;
    if (!isString(pathValue) || !pathValue) return false;
    if (!isBoolean(pushStateValue) || !isBoolean(replaceStateValue) || !isBoolean(forceValue)) return false;
    if (!isNullOrUndefined(parametersValue) && (!isObject(parametersValue) || !isRouteParameters(parametersValue))) return false;
    if (!isNullOrUndefined(routeValue) && (!isObject(routeValue) || !isRouteDefinition(routeValue))) return false;
    if (!isNullOrUndefined(metaValue) && !isJsonObject(metaValue)) return false;
    return true;
};

export { isNavigationRequest, isRouteDefinition, isRouteParameters };
