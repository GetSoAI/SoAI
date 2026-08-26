/* SoAI - Shared layout foundation [frontend/assets/ts/core/layout/sidebar/foundation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { isArray, isFunction, isObject, isString } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { FEATURES_SERVICE_PREFIX } from '@core/layout/sidebar/actions.ts';

const normalizeComponentToken = (name: string | null): string | null => {
    if (!isString(name)) return null;
    const token = name.trim();
    if (!token) return null;
    return token.startsWith(FEATURES_SERVICE_PREFIX) ? token : FEATURES_SERVICE_PREFIX + token;
};

const normalizeRoute = (routeValue: string | null | undefined): string => {
    if (!isString(routeValue)) return '';
    const trimmed = routeValue.trim();
    if (!trimmed) return '';
    const withoutHash = trimmed.startsWith('#') ? trimmed.slice(1) : trimmed;
    const withoutSlash = withoutHash.startsWith('/') ? withoutHash.slice(1) : withoutHash;
    const withoutQuery = withoutSlash.includes('?') ? (withoutSlash.split('?')[0] ?? '') : withoutSlash;
    return withoutQuery.trim();
};

const requireStringRecord = <T>(value: T, label: string): Record<string, string> => {
    if (!isObject(value) || isArray(value)) {
        throw new TypeError(`${label} must be a plain object`);
    }
    const out: Record<string, string> = {};
    for (const [key, entry] of Object.entries(value)) {
        if (entry === null || entry === undefined) {
            continue;
        }
        if (!isString(entry)) {
            throw new TypeError(`${label}.${key} must be a string`);
        }
        out[key] = entry;
    }
    return out;
};

const requireStringSet = (value: ReadonlySet<string> | null | undefined, label: string): Set<string> => {
    if (!(value instanceof Set)) {
        throw new TypeError(`${label} must be a Set`);
    }
    for (const entry of value.values()) {
        if (!isString(entry)) {
            throw new TypeError(`${label} must contain only strings`);
        }
    }
    return new Set(value);
};

class AsyncQueue {
    #tail: Promise<void>;

    constructor() {
        this.#tail = Promise.resolve();
    }

    run<T>(task: () => T | Promise<T>): Promise<T> {
        if (!isFunction(task)) return Promise.reject(new Error('AsyncQueue requires a task function'));
        const next = (async (): Promise<T> => {
            try {
                await this.#tail;
            } catch (tailError) {
                ensureError(tailError);
            }
            return task();
        })();
        this.#tail = (async (): Promise<void> => {
            try {
                await next;
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('Sidebar', 'AsyncQueue task failed', runtimeError);
            }
        })();
        return next;
    }
}

export { AsyncQueue, normalizeComponentToken, normalizeRoute, requireStringRecord, requireStringSet };
