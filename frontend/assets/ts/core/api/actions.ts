/* SoAI - Shared API actions [frontend/assets/ts/core/api/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LOGOUT_ENDPOINT } from '@core/api/constants.ts';
import { SETUP_REQUIRED_AUTH_EVENT, isSessionInvalidApiError, isSetupRequiredApiError } from '@core/auth/sessionFailure.ts';
import type { AuthManagerRuntime } from '@core/auth/runtime.ts';
import type { ConnectionState } from '@core/connectionstate/service.ts';
import { dispatchCustomEvent } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { toString } from '@core/normalize.ts';
import { isAbsoluteHttpUrl, resolveHttpUrl } from '@core/security/public.ts';
import { hasOwn, isArray, isNullOrUndefined, isObject } from '@core/typeGuards.ts';
import type { APIErrorMetadataValue } from '@core/apiError.ts';
import type { ApiQueryParameters, ApiQueryValue } from '@core/api/types/request.ts';

interface HandleAuthenticationFailureDependencies {
    waitForAuthService: () => Promise<AuthManagerRuntime | null>;
    logWarning: (message: string, error: Error) => void;
}

const appendQueryValue = (parameters: URLSearchParams, key: string, value: ApiQueryValue): void => {
    if (isArray(value)) {
        value.forEach((entry) => {
            if (!isNullOrUndefined(entry)) {
                parameters.append(key, toString(entry));
            }
        });
        return;
    }
    if (!isNullOrUndefined(value)) {
        parameters.append(key, toString(value));
    }
};

const applyQueryValues = (parameters: URLSearchParams, query: ApiQueryParameters): void => {
    for (const key in query) {
        if (!hasOwn(query, key)) {
            continue;
        }
        const value = query[key];
        if (isNullOrUndefined(value)) {
            continue;
        }
        parameters.delete(key);
        appendQueryValue(parameters, key, value);
    }
};

const buildRelativeApiUrl = (endpoint: string, query: ApiQueryParameters | null = null): string => {
    if (!endpoint) {
        throw new Error('ApiClient requires a valid endpoint');
    }
    if (isAbsoluteHttpUrl(endpoint)) {
        const absoluteEndpoint = resolveHttpUrl(endpoint);
        if (absoluteEndpoint === null) {
            throw new Error('ApiClient requires a valid absolute endpoint');
        }
        if (!query || !isObject(query)) {
            return absoluteEndpoint;
        }
        const absoluteUrl = new URL(absoluteEndpoint);
        applyQueryValues(absoluteUrl['searchParams'], query);
        return absoluteUrl.toString();
    }
    if (!query || !isObject(query)) {
        return endpoint;
    }

    const relativeEndpoint: string = endpoint;
    const queryIndex = relativeEndpoint.indexOf('?');
    const path = queryIndex === -1 ? relativeEndpoint : relativeEndpoint.slice(0, queryIndex);
    const existingQuery = queryIndex === -1 ? '' : relativeEndpoint.slice(queryIndex + 1);
    const parameters = new URLSearchParams(existingQuery);
    applyQueryValues(parameters, query);
    const queryString = parameters.toString();
    return queryString ? `${path}?${queryString}` : path;
};

const buildApiUrl = (endpoint: string, query: ApiQueryParameters | null, baseUrl: string | null): string => {
    const resolvedRelative = buildRelativeApiUrl(endpoint, query);
    if (isAbsoluteHttpUrl(resolvedRelative)) {
        const absoluteResolved = resolveHttpUrl(resolvedRelative);
        if (absoluteResolved === null) {
            throw new Error('ApiClient requires a valid absolute endpoint');
        }
        return absoluteResolved;
    }
    if (!baseUrl) {
        throw new Error('API baseUrl not set. Port discovery must complete before making API calls.');
    }
    return `${baseUrl}${resolvedRelative}`;
};

const buildUploadFormData = (file: Blob, additionalData: Record<string, string | Blob>, filenameOverride: string | null = null): FormData => {
    const formData = new FormData();
    for (const key in additionalData) {
        if (!hasOwn(additionalData, key)) {
            continue;
        }
        const value = additionalData[key];
        if (!isNullOrUndefined(value)) {
            formData.append(key, value);
        }
    }
    if (file.type && !hasOwn(additionalData, 'content_type')) {
        formData.append('content_type', file.type);
    }
    const normalizedFilename = filenameOverride && filenameOverride.trim() ? filenameOverride.trim() : null;
    if (normalizedFilename) {
        formData.append('file', file, normalizedFilename);
    } else {
        formData.append('file', file);
    }
    return formData;
};

const resolveDefaultApiBaseUrl = (connectionState: ConnectionState): string | null => connectionState.getBaseUrl() || connectionState.getConfiguredBaseUrl() || null;

const handleAuthenticationFailure = async (error: APIErrorMetadataValue, endpoint: string, dependencies: HandleAuthenticationFailureDependencies): Promise<void> => {
    if (isSetupRequiredApiError(error)) {
        dispatchCustomEvent(SETUP_REQUIRED_AUTH_EVENT, { endpoint });
        return;
    }
    if (!isSessionInvalidApiError(error) || endpoint === LOGOUT_ENDPOINT) {
        return;
    }
    const endpointValue = String(endpoint || '');
    const endpointPath = (() => {
        if (isAbsoluteHttpUrl(endpointValue)) {
            const resolvedEndpointUrl = resolveHttpUrl(endpointValue);
            if (resolvedEndpointUrl !== null) {
                return new URL(resolvedEndpointUrl).pathname || endpointValue;
            }
        }
        return endpointValue;
    })();
    if (endpointPath.startsWith('/v1/') || endpointPath === '/api/v1/openapi.json') {
        return;
    }
    try {
        const candidate = await dependencies.waitForAuthService();
        if (!candidate || !candidate.isAuthenticated) {
            return;
        }
        await candidate.invalidateSession();
    } catch (logoutError) {
        const runtimeError = ensureError(logoutError);
        dependencies.logWarning('Cross-tab logout triggered by auth error failed', runtimeError);
    }
};

export { buildApiUrl, buildRelativeApiUrl, buildUploadFormData, handleAuthenticationFailure, resolveDefaultApiBaseUrl };
export type { HandleAuthenticationFailureDependencies };
