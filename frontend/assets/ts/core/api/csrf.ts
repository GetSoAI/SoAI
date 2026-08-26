/* SoAI - Shared API csrf [frontend/assets/ts/core/api/csrf.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getGlobalScope, getLocation } from '@core/environment/public.ts';
import { isString } from '@core/typeGuards.ts';

const CSRF_HEADER_NAME = 'X-SoAI-CSRF';
const CSRF_UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

let csrfTokenFromApi: string | null = null;

const normalizeCsrfToken = (value: string | null): string | null => {
    const token = isString(value) ? value.trim() : '';
    return token ? token : null;
};

const resolveCsrfCookieName = (): string | null => {
    const protocol = getLocation().protocol.toLowerCase();
    if (protocol === 'http:') return 'soai-http-csrf';
    if (protocol === 'https:') return '__Host-soai-csrf';
    return null;
};

const readCurrentTransportCookie = (): string | null => {
    const cookieName = resolveCsrfCookieName();
    const documentRef = getGlobalScope().document;
    if (cookieName === null || !documentRef) return null;
    const prefix = `${cookieName}=`;
    for (const segment of documentRef.cookie.split(';')) {
        const text = segment.trim();
        if (text.startsWith(prefix)) return normalizeCsrfToken(text.slice(prefix.length));
    }
    return null;
};

const readCsrfToken = (): string | null => readCurrentTransportCookie() ?? csrfTokenFromApi;

const storeCsrfToken = (value: string | null): void => {
    const token = normalizeCsrfToken(value);
    if (token) {
        csrfTokenFromApi = token;
    }
};

const clearCsrfToken = (): void => {
    csrfTokenFromApi = null;
};

const syncCsrfTokenFromResponse = (response: Response): void => {
    storeCsrfToken(response.headers.get(CSRF_HEADER_NAME));
};

const hasHeader = (headers: Record<string, string>, name: string): boolean => {
    const normalizedName = name.toLowerCase();
    return Object.keys(headers).some((key) => key.toLowerCase() === normalizedName);
};

const applyCsrfHeader = (headers: Record<string, string>, method: string, credentials: RequestCredentials, includeCsrfHeader: boolean): void => {
    if (!includeCsrfHeader) {
        return;
    }
    if (!CSRF_UNSAFE_METHODS.has(method)) {
        return;
    }
    if (credentials === 'omit') {
        return;
    }
    if (hasHeader(headers, CSRF_HEADER_NAME)) {
        return;
    }
    const token = readCsrfToken();
    if (token) {
        headers[CSRF_HEADER_NAME] = token;
    }
};

const requestPathMatchesApiBasePath = (requestPath: string, apiPath: string): boolean => {
    const normalizedApiPath = apiPath.replace(/\/+$/, '');
    if (!normalizedApiPath) {
        return true;
    }
    return requestPath === normalizedApiPath || requestPath.startsWith(`${normalizedApiPath}/`);
};

const shouldAttachCsrfHeader = (requestUrl: string, apiBaseUrl: string | null): boolean => {
    const location = getLocation();
    const targetUrl = new URL(requestUrl, location.origin);
    if (apiBaseUrl) {
        const apiUrl = new URL(apiBaseUrl, location.origin);
        if (targetUrl.origin !== apiUrl.origin) {
            return false;
        }
        return requestPathMatchesApiBasePath(targetUrl.pathname, apiUrl.pathname);
    }
    return targetUrl.hostname === location.hostname;
};

export { CSRF_HEADER_NAME, applyCsrfHeader, clearCsrfToken, shouldAttachCsrfHeader, syncCsrfTokenFromResponse };
