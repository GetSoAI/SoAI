/* SoAI - Router navigation request validation and canonical URL serialization [frontend/assets/ts/core/routing/router/navigationRequest.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { NavigationOptions, NavigationRequest, NavigationTarget, QueryParameters, QueryParameterValue, RouteDefinition, RouteParameters } from '@core/routing/router/types.ts';
import { hasFunctionProperty, hasOwn, isArray, isBoolean, isNullOrUndefined, isObject, isString } from '@core/typeGuards.ts';
import { isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface RouteLayoutCandidate {
    hideSidebar?: boolean | undefined;
    scrollToTopAction?: boolean | undefined;
}

interface RouteDefinitionCandidate {
    path?: string | undefined;
    component?: string | undefined;
    getTitle?: (() => string) | undefined;
    layout?: RouteLayoutCandidate | null | undefined;
}

const isRouteDefinition = (value: RouteDefinitionCandidate): value is RouteDefinition => {
    const layout = 'layout' in value ? value.layout : null;
    return 'path' in value && isString(value.path) && Boolean(value.path) && 'component' in value && isString(value.component) && Boolean(value.component) && hasFunctionProperty(value, 'getTitle') && isObject(layout) && 'hideSidebar' in layout && isBoolean(layout.hideSidebar) && 'scrollToTopAction' in layout && isBoolean(layout.scrollToTopAction);
};

const normalizeRouteParameters = (value: RouteParameters | JsonObject): RouteParameters => {
    const parameters: RouteParameters = {};
    for (const [key, entry] of Object.entries(value)) {
        if (!isString(entry)) {
            throw new TypeError(`Route param ${key} must be a string`);
        }
        parameters[key] = entry;
    }
    return parameters;
};

const normalizeNavigationMeta = (value: JsonObject | null | undefined): JsonObject => {
    if (!isObject(value) || isArray(value)) {
        throw new TypeError('meta must be an object');
    }
    const normalized: JsonObject = {};
    for (const [key, entry] of Object.entries(value)) {
        if (!isJsonValue(entry)) {
            throw new TypeError(`Navigation meta ${key} must be a JSON value`);
        }
        normalized[key] = entry;
    }
    return normalized;
};

const normalizeQueryParameterValue = (value: QueryParameterValue | JsonValue): QueryParameterValue => {
    if (isNullOrUndefined(value)) {
        return value === null ? null : undefined;
    }
    if (isString(value) || typeof value === 'number' || typeof value === 'boolean') {
        return value;
    }
    if (isArray(value)) {
        const normalized: Array<string | number | boolean | null | undefined> = [];
        for (const entry of value) {
            if (isArray(entry)) {
                throw new TypeError('Nested query arrays are not supported');
            }
            if (entry === null) {
                normalized.push(null);
                continue;
            }
            if (entry === undefined) {
                normalized.push(undefined);
                continue;
            }
            if (isString(entry) || typeof entry === 'number' || typeof entry === 'boolean') {
                normalized.push(entry);
                continue;
            }
            throw new TypeError('Query array entries must be string, number, boolean, null, or undefined');
        }
        return normalized;
    }
    throw new TypeError('Query values must be string, number, boolean, null, undefined, or arrays of those');
};

const normalizeQueryParameters = (value: QueryParameters | JsonObject): QueryParameters => {
    const normalized: QueryParameters = {};
    for (const [key, entry] of Object.entries(value)) {
        normalized[key] = normalizeQueryParameterValue(entry);
    }
    return normalized;
};

const normalizeOptionsMap = (options: NavigationOptions): { options: Omit<NavigationOptions, 'query'>; query: QueryParameters } => {
    if (!isObject(options) || isArray(options)) throw new TypeError('navigation options must be an object');

    const normalized: Omit<NavigationOptions, 'query'> = {};
    const query: QueryParameters = {};
    const pushStateValue = options['pushState'];
    if (!isNullOrUndefined(pushStateValue)) {
        if (!isBoolean(pushStateValue)) throw new TypeError('pushState must be boolean');
        normalized.pushState = pushStateValue;
    }
    const replaceValue = options['replace'];
    if (!isNullOrUndefined(replaceValue)) {
        if (!isBoolean(replaceValue)) throw new TypeError('replace must be boolean');
        normalized.replace = replaceValue;
    }
    const forceValue = options['force'];
    if (!isNullOrUndefined(forceValue)) {
        if (!isBoolean(forceValue)) throw new TypeError('force must be boolean');
        normalized.force = forceValue;
    }
    const parametersValue = options['parameters'];
    if (!isNullOrUndefined(parametersValue)) {
        if (!isObject(parametersValue) || isArray(parametersValue)) throw new TypeError('parameters must be an object');
        normalized.parameters = normalizeRouteParameters(parametersValue);
    }
    const routeValue = options['route'];
    if (!isNullOrUndefined(routeValue)) {
        if (!isObject(routeValue) || !isRouteDefinition(routeValue)) throw new TypeError('route must be a RouteDefinition');
        normalized.route = routeValue;
    }
    const queryValue = options['query'];
    if (!isNullOrUndefined(queryValue)) {
        if (!isObject(queryValue) || isArray(queryValue)) throw new TypeError('query must be an object');
        Object.assign(query, normalizeQueryParameters(queryValue));
    }
    const pathValue = options['path'];
    if (!isNullOrUndefined(pathValue)) {
        if (!isString(pathValue)) throw new TypeError('path must be string');
        normalized.path = pathValue;
    }
    const metaValue = options['meta'];
    if (!isNullOrUndefined(metaValue)) {
        if (!isObject(metaValue) || isArray(metaValue)) throw new TypeError('meta must be an object');
        normalized.meta = normalizeNavigationMeta(metaValue);
    }
    return { options: normalized, query };
};

const buildNavigationPath = (path: string, query: QueryParameters): string => {
    const parameters = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
        if (isNullOrUndefined(value)) continue;
        if (isArray(value)) {
            for (const entry of value) {
                if (!isNullOrUndefined(entry)) parameters.append(key, String(entry));
            }
            continue;
        }
        parameters.append(key, String(value));
    }
    const queryString = parameters.toString();
    if (!queryString) return path;
    return `${path}${path.includes('?') ? '&' : '?'}${queryString}`;
};

const serializeRouteParameters = (path: string, routeParameters: RouteParameters): string => {
    const queryStartIndex = path.indexOf('?');
    const routePath = queryStartIndex === -1 ? path : path.slice(0, queryStartIndex);
    const existingQuery = queryStartIndex === -1 ? '' : path.slice(queryStartIndex + 1);
    const serializedQuery = new URLSearchParams(existingQuery);
    const routeSegments = routePath.split('/').map((segment) => {
        if (!segment.startsWith(':')) return segment;
        const parameterName = segment.slice(1);
        const parameterValue = routeParameters[parameterName];
        if (!hasOwn(routeParameters, parameterName) || !isString(parameterValue)) throw new Error(`Router requires route parameter: ${parameterName}`);
        return encodeURIComponent(parameterValue);
    });
    const consumedParameterNames = new Set(
        routePath
            .split('/')
            .filter((segment) => segment.startsWith(':'))
            .map((segment) => segment.slice(1))
    );
    for (const [parameterName, value] of Object.entries(routeParameters)) {
        if (!consumedParameterNames.has(parameterName)) serializedQuery.set(parameterName, value);
    }
    const queryString = serializedQuery.toString();
    const serializedPath = routeSegments.join('/');
    return queryString ? `${serializedPath}?${queryString}` : serializedPath;
};

const normalizeNavigationRequest = (target: string | NavigationTarget, options: NavigationOptions = {}): NavigationRequest => {
    const normalized = normalizeOptionsMap(options);
    const normalizedOptions = normalized.options;
    let pathInput: string | null = null;
    const mergedParameters: RouteParameters = {};
    if (isString(target)) {
        pathInput = target;
    } else if (isObject(target)) {
        const pathValue = target['path'];
        if (isString(pathValue)) pathInput = pathValue;
        const parametersValue = target['parameters'];
        if (!isNullOrUndefined(parametersValue)) {
            if (!isObject(parametersValue) || isArray(parametersValue)) throw new TypeError('target.parameters must be an object');
            Object.assign(mergedParameters, normalizeRouteParameters(parametersValue));
        }
        const routeValue = target['route'];
        if (!isNullOrUndefined(routeValue)) {
            if (!isObject(routeValue) || !isRouteDefinition(routeValue)) throw new TypeError('target.route must be a RouteDefinition');
            normalizedOptions.route = routeValue;
        }
        const metaValue = target['meta'];
        if (!isNullOrUndefined(metaValue)) {
            if (!isObject(metaValue)) throw new TypeError('target.meta must be an object');
            normalizedOptions.meta = normalizeNavigationMeta(metaValue);
        }
    }
    if (!pathInput && isString(normalizedOptions.path)) pathInput = normalizedOptions.path;
    const trimmedPath = toTrimmedString(pathInput);
    if (!trimmedPath) throw new Error('Router requires a target path');
    if (normalizedOptions.parameters) Object.assign(mergedParameters, normalizedOptions.parameters);
    return {
        path: serializeRouteParameters(buildNavigationPath(trimmedPath, normalized.query), mergedParameters),
        pushState: normalizedOptions.pushState !== false,
        replaceState: normalizedOptions.replace === true,
        force: normalizedOptions.force === true,
        parameters: null,
        route: normalizedOptions.route ?? null,
        meta: normalizedOptions.meta ?? null
    };
};

export { normalizeNavigationMeta, normalizeNavigationRequest };
