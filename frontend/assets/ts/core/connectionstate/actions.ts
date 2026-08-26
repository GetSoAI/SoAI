/* SoAI - Shared connection state actions [frontend/assets/ts/core/connectionstate/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { hasOwn, isFunction, isNullOrUndefined, isObject, isString } from '@core/typeGuards.ts';
import { getLocation } from '@core/environment/public.ts';
import { sanitizeForId } from '@core/identifiers.ts';
import { type BaseUrlListener, type StorageService, type UpdateOptions, type Waiter } from '@core/connectionstate/contracts.ts';
import type { ConnectionStateState } from '@core/connectionstate/state.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { decodeConnectionEndpoint, encodeConnectionEndpoint, type ConnectionEndpoint } from '@core/connectionstate/connectionEndpoint.ts';

const resolveStorageKey = (): string => {
    const hostname = getLocation().hostname;
    if (!isString(hostname) || !hostname.trim()) {
        throw new Error('Location hostname must be a non-empty string');
    }
    return `connection_base_url_${sanitizeForId(hostname)}`;
};

const readPersistedEndpoint = (storage: StorageService, storageKey: string): ConnectionEndpoint | null => {
    if (!isFunction(storage.get)) {
        throw new Error('Storage service must expose get for connection state persistence');
    }
    return decodeConnectionEndpoint(storage.get(storageKey));
};

const persistEndpoint = (storage: StorageService, storageKey: string, endpoint: ConnectionEndpoint | null): void => {
    if (!isFunction(storage.set)) {
        throw new Error('Storage service must expose set for connection state persistence');
    }
    storage.set(storageKey, endpoint ? encodeConnectionEndpoint(endpoint) : null);
};

const notifyListeners = (listeners: Set<BaseUrlListener>, value: string | null, logWarn: (message: string, error: Error) => void): void => {
    if (!listeners.size) {
        return;
    }
    const snapshot = Array.from(listeners);
    snapshot.forEach((listener) => {
        try {
            listener(value);
        } catch (error) {
            const runtimeError = ensureError(error);
            logWarn('Listener execution failed', runtimeError);
        }
    });
};

const resolveWaiters = (waiters: Set<Waiter>, value: string | null, logWarn: (message: string, error: Error) => void): void => {
    if (!waiters.size || !value) {
        return;
    }
    const pending = Array.from(waiters);
    waiters.clear();
    pending.forEach((waiter) => {
        try {
            waiter.cleanup?.();
            waiter.resolve(value);
        } catch (error) {
            const runtimeError = ensureError(error);
            logWarn('Waiter resolution failed', runtimeError);
        }
    });
};

const updateBaseUrl = (
    state: ConnectionStateState,
    value: string | null,
    options: UpdateOptions,
    callbacks: {
        notifyListeners: (value: string | null) => void;
        resolveWaiters: (value: string | null) => void;
    }
): string | null => {
    const nextValue = value ?? null;
    const nextInstanceId = nextValue ? (options.instanceId === undefined && state.baseUrl === nextValue ? state.instanceId : options.instanceId?.trim() || null) : options.releaseConfigured ? null : state.instanceId;

    if (state.baseUrl === nextValue && state.instanceId === nextInstanceId) {
        if (nextValue === null && options.releaseConfigured) {
            state.allowConfiguredFallback = false;
            state.persistedBaseUrl = null;
            persistEndpoint(state.storage, state.storageKey, null);
        }
        return state.baseUrl;
    }

    state.baseUrl = nextValue;
    state.instanceId = nextInstanceId;
    if (state.baseUrl && state.instanceId) {
        persistEndpoint(state.storage, state.storageKey, {
            baseUrl: state.baseUrl,
            instanceId: state.instanceId
        });
        state.persistedBaseUrl = state.baseUrl;
    } else if (options.releaseConfigured) {
        persistEndpoint(state.storage, state.storageKey, null);
        state.persistedBaseUrl = null;
        state.allowConfiguredFallback = false;
    }

    if (!options.silent) {
        callbacks.notifyListeners(state.baseUrl);
    }
    callbacks.resolveWaiters(state.baseUrl);

    return state.baseUrl;
};

const captureConfiguredBaseUrl = (
    state: ConnectionStateState,
    options: {
        normalizeBaseUrl: (value: string) => string | null;
    }
): string | null => {
    state.allowConfiguredFallback = true;

    const persisted = readPersistedEndpoint(state.storage, state.storageKey);
    if (persisted) {
        const normalized = options.normalizeBaseUrl(persisted.baseUrl);
        if (normalized) {
            state.persistedBaseUrl = normalized;
            state.instanceId = persisted.instanceId;
            persistEndpoint(state.storage, state.storageKey, {
                baseUrl: state.persistedBaseUrl,
                instanceId: state.instanceId
            });
            return state.persistedBaseUrl;
        }
        persistEndpoint(state.storage, state.storageKey, null);
    }

    state.persistedBaseUrl = null;
    return state.runtimeConfiguredBaseUrl;
};

const applyStorageSnapshot = (
    state: ConnectionStateState,
    snapshot: JsonValue,
    callbacks: {
        normalizeBaseUrl: (value: string) => string | null;
        updateBaseUrl: (value: string | null, options: UpdateOptions) => string | null;
    }
): string | null | undefined => {
    if (!isObject(snapshot)) {
        throw new TypeError('Storage snapshot must be an object');
    }

    const cache = snapshot['cache'];
    if (!isObject(cache)) {
        throw new Error('Storage snapshot must include cache object');
    }

    const misc = cache['misc'];
    if (!isObject(misc)) {
        throw new Error('Storage snapshot must include misc object');
    }

    const raw = hasOwn(misc, state.snapshotStorageKey) ? misc[state.snapshotStorageKey] : null;
    if (raw === null || isNullOrUndefined(raw)) {
        if (state.baseUrl === null) {
            return;
        }
        return callbacks.updateBaseUrl(null, { releaseConfigured: true });
    }

    const endpoint = decodeConnectionEndpoint(raw);
    if (!endpoint) {
        throw new TypeError('Connection endpoint in storage snapshot is invalid');
    }

    const normalized = callbacks.normalizeBaseUrl(endpoint.baseUrl);
    if (state.baseUrl === normalized && state.instanceId === endpoint.instanceId) {
        return state.baseUrl;
    }

    return callbacks.updateBaseUrl(normalized, {
        silent: false,
        instanceId: endpoint.instanceId
    });
};

export { resolveStorageKey, readPersistedEndpoint, persistEndpoint, notifyListeners, resolveWaiters, updateBaseUrl, captureConfiguredBaseUrl, applyStorageSnapshot };
