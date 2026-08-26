/* SoAI - Shared realtime transport security [frontend/assets/ts/core/realtime/transportSecurity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLocation } from '@core/environment/public.ts';
import { isNullOrUndefined, isObject, isString } from '@core/typeGuards.ts';

interface LocationContract {
    protocol?: string;
    href?: string;
    host?: string;
    hostname?: string;
    pathname?: string;
    search?: string;
    hash?: string;
}

interface ScopeContract {
    location?: LocationContract;
}

type TransportSecurityScope = ScopeContract | null | undefined;

const resolveScope = (scope: ScopeContract): ScopeContract => {
    if (!isObject(scope)) {
        throw new Error('Transport security scope must be an object');
    }
    return scope;
};

const resolveLocation = (scope: TransportSecurityScope): LocationContract => {
    if (isNullOrUndefined(scope)) {
        return getLocation();
    }
    const context = resolveScope(scope);
    const { location } = context;
    if (isNullOrUndefined(location) || !isObject(location)) {
        throw new Error('Location context is required for transport security operations');
    }
    return location;
};

const getWebSocketProtocol = (httpProtocol: string): 'wss:' | 'ws:' => {
    const protocol = httpProtocol.trim().toLowerCase();
    if (!protocol) {
        throw new Error('HTTP protocol must be defined for WebSocket protocol resolution');
    }
    if (protocol === 'https:') {
        return 'wss:';
    }
    if (protocol === 'http:') {
        return 'ws:';
    }
    throw new Error(`Unsupported protocol ${protocol} for WebSocket resolution`);
};

const LOCALHOST_HOSTNAMES: ReadonlySet<string> = Object.freeze(new Set(['localhost', '127.0.0.1', '::1']));

const normalizeHostname = (hostname: string): string => {
    const normalized = hostname.trim().toLowerCase();
    if (normalized.startsWith('[') && normalized.endsWith(']')) {
        return normalized.slice(1, -1);
    }
    return normalized;
};

const parseHostnameFromUrl = (url: string): string => {
    try {
        return new URL(url).hostname;
    } catch (error) {
        throw new Error(`Invalid URL for hostname parsing: ${String(error)}`);
    }
};

const isLocalhostHostname = (hostname: string): boolean => {
    const normalizedHostname = normalizeHostname(hostname);
    return LOCALHOST_HOSTNAMES.has(normalizedHostname);
};

const isSecureContext = (scope?: TransportSecurityScope): boolean => {
    const location = resolveLocation(scope);
    const protocol = isString(location.protocol) ? location.protocol.trim().toLowerCase() : '';

    if (protocol === 'https:') {
        return true;
    }

    if (protocol === 'http:') {
        const rawHostname = isString(location.hostname) ? location.hostname : '';
        if (rawHostname) {
            return isLocalhostHostname(rawHostname);
        }

        const href = isString(location.href) ? location.href.trim() : '';
        if (href) {
            return isLocalhostHostname(parseHostnameFromUrl(href));
        }

        const host = isString(location.host) ? location.host.trim() : '';
        if (!host) {
            return false;
        }
        return isLocalhostHostname(parseHostnameFromUrl(`${protocol}//${host}`));
    }

    return false;
};

const allowsInsecureTransport = (scope?: TransportSecurityScope): boolean => {
    const location = resolveLocation(scope);
    const protocol = isString(location.protocol) ? location.protocol.trim().toLowerCase() : '';
    if (!protocol) {
        throw new Error('Location protocol must be defined for transport security');
    }
    if (protocol === 'https:' || protocol === 'http:') {
        return true;
    }
    throw new Error(`Unsupported protocol ${protocol} for transport security`);
};

export { getWebSocketProtocol, isSecureContext, allowsInsecureTransport };
