/* SoAI - Frontend runtime configuration ownership [frontend/assets/ts/core/runtimeconfiguration/runtimeConfiguration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolve } from '@core/dom/dom.ts';
import { getDocument, getGlobalScope, getLocation } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { resolveTelemetryDebugFlag } from '@core/runtimeconfiguration/telemetryDebug.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isBoolean, isNullOrUndefined, isObject, isString, hasOwn } from '@core/typeGuards.ts';

interface LocationInterface {
    origin: string;
    search: string;
}

interface RuntimeConfig {
    apiBaseUrl?: string | null;
    discoveryPorts?: JsonValue | null | undefined;
    telemetryDebug?: boolean;
}

interface FrozenRuntimeConfig {
    apiBaseUrl: string | null;
    telemetryDebug: boolean;
    discoveryPorts: readonly number[];
}

const RUNTIME_CONFIG_GLOBAL = '__SOAI_RUNTIME_CONFIG__';
const RUNTIME_ENTRY_SELECTOR = 'script[data-soai-entry]';
const RUNTIME_ATTRIBUTE = 'data-soai-runtime';

const ensureLocation = (): LocationInterface => {
    const location = getLocation();
    if (!isString(location.origin) || !location.origin.trim()) {
        throw new Error('Window location origin must be a non-empty string');
    }
    return location;
};

const normalizeApiBaseUrl = (value: JsonValue | null | undefined, location: LocationInterface = ensureLocation()): string => {
    if (isNullOrUndefined(value)) {
        throw new Error('API base URL must be provided');
    }
    const raw = String(value).trim();
    if (!raw) {
        throw new Error('API base URL must be a non-empty string');
    }

    let parsed: URL;
    try {
        parsed = new URL(raw, location.origin);
    } catch (_error) {
        throw new Error(`Invalid API base URL: ${raw}`);
    }
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        throw new Error(`API base URL must use HTTP or HTTPS: ${raw}`);
    }

    const currentLocationUrl = new URL(location.origin);
    if (parsed.host === currentLocationUrl.host && parsed.protocol !== currentLocationUrl.protocol) {
        parsed.protocol = currentLocationUrl.protocol;
    }

    parsed.search = '';
    parsed.hash = '';

    let path = parsed.pathname ?? '';
    path = path.replace(/\/+$/, '');
    if (path) {
        const normalized = path.toLowerCase();
        if (normalized === '/api' || normalized === '/api/v1') {
            path = '';
        } else if (normalized.endsWith('/api/v1')) {
            path = path.slice(0, -7);
        } else if (normalized.endsWith('/api')) {
            path = path.slice(0, -4);
        }
        path = path.replace(/\/+$/, '');
    }

    if (!path || path === '/') {
        return parsed.origin;
    }
    return `${parsed.origin}${path}`;
};

const normalizeDiscoveryPorts = (value: JsonValue | null | undefined): readonly number[] => {
    if (isNullOrUndefined(value)) {
        return Object.freeze([]);
    }
    const source = isArray(value) ? value : [value];
    const normalized: number[] = [];
    source.forEach((entry) => {
        const entryString = String(entry);
        const parsed = Number.parseInt(entryString, 10);
        if (!Number.isInteger(parsed) || parsed <= 0) {
            throw new Error(`Discovery ports must contain positive integers. Received: ${entryString}`);
        }
        normalized.push(parsed);
    });
    const unique = Array.from(new Set(normalized));
    return Object.freeze(unique);
};

const parseRuntimeConfigSeed = (candidate: JsonValue | null | undefined, source: string): RuntimeConfig | null => {
    if (!candidate || !isObject(candidate)) {
        return null;
    }

    const seed: RuntimeConfig = {};
    if (hasOwn(candidate, 'apiBaseUrl')) {
        const apiBaseUrlValue = candidate['apiBaseUrl'];
        if (apiBaseUrlValue === null) {
            seed.apiBaseUrl = null;
        } else if (isString(apiBaseUrlValue)) {
            seed.apiBaseUrl = apiBaseUrlValue;
        } else if (!isNullOrUndefined(apiBaseUrlValue)) {
            throw new Error(`${source}: apiBaseUrl must be a string, null, or omitted`);
        }
    }
    if (hasOwn(candidate, 'telemetryDebug')) {
        const telemetryDebugValue = candidate['telemetryDebug'];
        if (isBoolean(telemetryDebugValue)) {
            seed.telemetryDebug = telemetryDebugValue;
        } else if (!isNullOrUndefined(telemetryDebugValue)) {
            throw new Error(`${source}: telemetryDebug must be a boolean or omitted`);
        }
    }
    if (hasOwn(candidate, 'discoveryPorts')) {
        seed.discoveryPorts = candidate['discoveryPorts'];
    }
    return seed;
};

const readRuntimeConfigFromGlobal = (): RuntimeConfig | null => {
    const scope = getGlobalScope();
    const candidate = scope ? scope[RUNTIME_CONFIG_GLOBAL] : null;
    return isJsonValue(candidate) ? parseRuntimeConfigSeed(candidate, 'Global runtime configuration') : null;
};

const readRuntimeConfigFromAttribute = (): RuntimeConfig | null => {
    let documentRef: Document;
    try {
        documentRef = getDocument();
    } catch (error) {
        getGlobalScope()?.console?.warn?.('RuntimeConfiguration: document unavailable for inline config', error);
        throw ensureError(error);
    }
    const script = resolve(`${RUNTIME_ENTRY_SELECTOR}[${RUNTIME_ATTRIBUTE}]`, documentRef);
    if (!script) {
        return null;
    }
    const raw = script.getAttribute(RUNTIME_ATTRIBUTE);
    if (!raw) {
        return null;
    }
    try {
        const parsedValue = parseRequiredJsonText(raw);
        return parseRuntimeConfigSeed(parsedValue, 'Inline runtime configuration');
    } catch (error) {
        const runtimeError = ensureError(error);
        getGlobalScope()?.console?.error?.('RuntimeConfiguration: parsing inline config failed', runtimeError);
        throw ensureError(error);
    }
};

let runtimeConfigSeed: RuntimeConfig | null | undefined = undefined;

const getRuntimeConfigSeed = (): RuntimeConfig | null => {
    if (runtimeConfigSeed !== undefined) {
        return runtimeConfigSeed;
    }
    runtimeConfigSeed = readRuntimeConfigFromGlobal() ?? readRuntimeConfigFromAttribute() ?? null;
    return runtimeConfigSeed;
};

const normalizeConfiguredApiBaseUrl = (value: JsonValue | null | undefined, location: LocationInterface = ensureLocation()): string | null => {
    if (isNullOrUndefined(value)) {
        return null;
    }
    if (isString(value)) {
        const trimmed = value.trim();
        if (!trimmed || trimmed.toLowerCase() === 'auto') {
            return null;
        }
        return normalizeApiBaseUrl(trimmed, location);
    }
    return normalizeApiBaseUrl(value, location);
};

const deriveDefaultConfiguration = (): RuntimeConfig => {
    const location = ensureLocation();
    const seed = getRuntimeConfigSeed();
    const baseCandidate = seed && hasOwn(seed, 'apiBaseUrl') ? seed.apiBaseUrl : 'auto';
    const discoveryCandidate = seed && hasOwn(seed, 'discoveryPorts') ? seed.discoveryPorts : undefined;
    const apiBaseUrl = normalizeConfiguredApiBaseUrl(baseCandidate, location);
    return {
        apiBaseUrl,
        telemetryDebug: resolveTelemetryDebugFlag(location),
        discoveryPorts: normalizeDiscoveryPorts(discoveryCandidate)
    };
};

const freezeRuntimeConfiguration = (input: JsonValue | null | undefined): FrozenRuntimeConfig => {
    if (!isObject(input)) {
        throw new Error('Runtime configuration must be an object');
    }
    const location = ensureLocation();
    const basePreference = hasOwn(input, 'apiBaseUrl') ? input['apiBaseUrl'] : 'auto';
    const apiBaseUrl = normalizeConfiguredApiBaseUrl(basePreference, location);
    const telemetryDebug = hasOwn(input, 'telemetryDebug') && input['telemetryDebug'] === true;
    const discoveryPorts = normalizeDiscoveryPorts(hasOwn(input, 'discoveryPorts') ? input['discoveryPorts'] : undefined);
    return Object.freeze({
        apiBaseUrl,
        telemetryDebug,
        discoveryPorts
    });
};

const runtimeConfigToJson = (config: RuntimeConfig): JsonValue => ({
    ...(config.apiBaseUrl !== undefined ? { apiBaseUrl: config.apiBaseUrl } : {}),
    ...(config.telemetryDebug !== undefined ? { telemetryDebug: config.telemetryDebug } : {}),
    ...(config.discoveryPorts !== undefined ? { discoveryPorts: config.discoveryPorts } : {})
});

let runtimeConfiguration: FrozenRuntimeConfig | null = null;

const getOrCreateRuntimeConfiguration = (): FrozenRuntimeConfig => {
    if (!runtimeConfiguration) {
        runtimeConfiguration = freezeRuntimeConfiguration(runtimeConfigToJson(deriveDefaultConfiguration()));
    }
    return runtimeConfiguration;
};
const getApiBaseUrl = (): string | null => getOrCreateRuntimeConfiguration().apiBaseUrl;
const isTelemetryDebugEnabled = (): boolean => getOrCreateRuntimeConfiguration().telemetryDebug;
const getDiscoveryPorts = (): readonly number[] => getOrCreateRuntimeConfiguration().discoveryPorts;

const resetRuntimeConfigurationForTesting = (input?: JsonValue | null | undefined): FrozenRuntimeConfig | null => {
    runtimeConfiguration = null;
    if (input !== undefined) {
        runtimeConfiguration = freezeRuntimeConfiguration(input);
    }
    return runtimeConfiguration;
};

export { resetRuntimeConfigurationForTesting, getApiBaseUrl, getDiscoveryPorts, normalizeConfiguredApiBaseUrl, isTelemetryDebugEnabled, normalizeApiBaseUrl };
