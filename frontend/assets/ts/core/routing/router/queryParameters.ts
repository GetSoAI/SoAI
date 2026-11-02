/* SoAI - Pure route query construction and consumption [frontend/assets/ts/core/routing/router/queryParameters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const buildQueryRoute = (path: string, queryParameters: Record<string, string> = {}): string => {
    const queryString = new URLSearchParams(queryParameters).toString();
    return queryString ? `${path}?${queryString}` : path;
};

const buildRouteWithoutQueryParameters = (path: string, queryParameters: Record<string, string>, excludedKeys: readonly string[]): string => {
    const queryStart = path.indexOf('?');
    const basePath = queryStart < 0 ? path : path.slice(0, queryStart);
    const excluded = new Set(excludedKeys);
    const nextParameters = new URLSearchParams();
    for (const [key, value] of Object.entries(queryParameters)) {
        if (!excluded.has(key)) {
            nextParameters.append(key, value);
        }
    }
    const queryString = nextParameters.toString();
    return queryString ? `${basePath}?${queryString}` : basePath;
};

const getQueryParametersFromHash = (hash: string): Record<string, string> => {
    const queryStart = hash.indexOf('?');
    const queryString = queryStart < 0 ? '' : hash.slice(queryStart + 1);
    return queryString ? Object.fromEntries(new URLSearchParams(queryString)) : {};
};

export { buildQueryRoute, buildRouteWithoutQueryParameters, getQueryParametersFromHash };
