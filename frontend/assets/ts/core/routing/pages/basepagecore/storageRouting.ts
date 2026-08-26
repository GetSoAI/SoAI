/* SoAI - Storage-backed route persistence [frontend/assets/ts/core/routing/pages/basepagecore/storageRouting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { AuthManager } from '@core/auth/public.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { RouteParameters } from '@core/routing/router/types.ts';
import { request, requestFunctionValue } from '@core/routing/pages/basepagecore/actions.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const normalizeRouteParameters = (parameters: Record<string, string | null | undefined>): RouteParameters | undefined => {
    const normalized: RouteParameters = {};
    for (const [key, value] of Object.entries(parameters)) {
        if (value !== null && value !== undefined) {
            normalized[key] = value;
        }
    }
    return Object.keys(normalized).length ? normalized : undefined;
};

const savePageStorageValue = (storage: Pick<StorageService, 'set'> | null | undefined, key: string, value: JsonValue | null | undefined): void => {
    requestFunctionValue(request(storage, 'Storage'), 'set', 'Storage')(key, value);
};

const loadPageStorageValue = (storage: Pick<StorageService, 'get'> | null | undefined, key: string, defaultValue: JsonValue | null | undefined): JsonValue | null => {
    return requestFunctionValue(request(storage, 'Storage'), 'get', 'Storage')(key, defaultValue) ?? null;
};

const removePageStorageValue = (storage: Pick<StorageService, 'remove'> | null | undefined, key: string): void => {
    requestFunctionValue(request(storage, 'Storage'), 'remove', 'Storage')(key);
};

const navigatePageRoute = (router: Pick<Router, 'navigate'> | null | undefined, pageId: string, parameters: Record<string, string | null | undefined>): void => {
    const normalizedParameters = normalizeRouteParameters(parameters);
    terminateHandledPromise(requestFunctionValue(request(router, 'Router'), 'navigate', 'Router')(pageId, normalizedParameters ? { parameters: normalizedParameters } : {}));
};

const getPageCurrentRoute = (router: Pick<Router, 'getCurrentRoute'> | null | undefined): string | null => {
    return requestFunctionValue(request(router, 'Router'), 'getCurrentRoute', 'Router')() ?? null;
};

const resolvePageAuthenticated = (auth: Pick<AuthManager, 'isAuthenticated'> | null | undefined): boolean => {
    return auth?.isAuthenticated === true;
};

export { getPageCurrentRoute, loadPageStorageValue, navigatePageRoute, removePageStorageValue, resolvePageAuthenticated, savePageStorageValue };
