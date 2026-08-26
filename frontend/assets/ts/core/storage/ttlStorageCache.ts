/* SoAI - Expiring storage cache with TTL enforcement [frontend/assets/ts/core/storage/ttlStorageCache.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { isNumber, isObject, hasOwn } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type StorageArea = 'localStorage' | 'sessionStorage';

interface StorageTextAdapter {
    getItem: (key: string) => string | null;
    setItem: (key: string, value: string) => void;
    removeItem: (key: string) => void;
}

type Validator<T extends JsonValue | null> = (value: JsonValue | null) => value is T;

type TtlStorageEntry<T> = Readonly<{
    value: T;
    timestamp: number;
}>;

const resolveStorage = (area: StorageArea): Storage | null => {
    try {
        return area === 'localStorage' ? localStorage : sessionStorage;
    } catch (storageError) {
        errorHandler.debug('ttlStorageCache', 'Storage unavailable', { area, error: storageError });
        throw ensureError(storageError);
    }
};

const readRaw = (area: StorageArea, key: string): string | null => {
    const storage = resolveStorage(area);
    if (!storage) return null;
    try {
        return storage.getItem(key);
    } catch (storageError) {
        errorHandler.debug('ttlStorageCache', 'Failed to read key', { key, error: storageError });
        throw ensureError(storageError);
    }
};

const writeRaw = (area: StorageArea, key: string, value: string): boolean => {
    const storage = resolveStorage(area);
    if (!storage) return false;
    try {
        storage.setItem(key, value);
        return true;
    } catch (storageError) {
        errorHandler.debug('ttlStorageCache', 'Failed to write key', { key, error: storageError });
        throw ensureError(storageError);
    }
};

export const readStorageText = (area: StorageArea, key: string): string | null => readRaw(area, key);

export const writeStorageText = (area: StorageArea, key: string, value: string): boolean => writeRaw(area, key, value);

export const removeStorageKey = (area: StorageArea, key: string): boolean => {
    const storage = resolveStorage(area);
    if (!storage) return false;
    try {
        storage.removeItem(key);
        return true;
    } catch (storageError) {
        errorHandler.debug('ttlStorageCache', 'Failed to remove key', { key, error: storageError });
        throw ensureError(storageError);
    }
};

export const createStorageTextAdapter = (area: StorageArea): StorageTextAdapter => ({
    getItem: (key: string): string | null => readStorageText(area, key),
    setItem: (key: string, value: string): void => {
        if (!writeStorageText(area, key, value)) {
            throw new Error(`Unable to write ${area} key ${key}`);
        }
    },
    removeItem: (key: string): void => {
        if (!removeStorageKey(area, key)) {
            throw new Error(`Unable to remove ${area} key ${key}`);
        }
    }
});

export const readStorageJson = (area: StorageArea, key: string): JsonValue | null => {
    const raw = readRaw(area, key);
    if (!raw) return null;
    try {
        return parseRequiredJsonText(raw);
    } catch (storageError) {
        errorHandler.debug('ttlStorageCache', 'Failed to parse JSON for key', { key, error: storageError });
        throw ensureError(storageError);
    }
};

export const writeStorageJson = (area: StorageArea, key: string, value: JsonValue | null): boolean => {
    try {
        return writeRaw(area, key, JSON.stringify(value));
    } catch (storageError) {
        errorHandler.debug('ttlStorageCache', 'Failed to stringify JSON for key', { key, error: storageError });
        throw ensureError(storageError);
    }
};

const isTtlStorageEntry = (value: JsonValue | null): value is { value: JsonValue | null; timestamp: number } => {
    if (!isObject(value)) return false;
    const objectValue = value;
    return hasOwn(objectValue, 'value') && isNumber(objectValue['timestamp']);
};

export function readTtlStorageEntry(area: StorageArea, key: string, ttlMs: number): TtlStorageEntry<JsonValue | null> | null;
export function readTtlStorageEntry<T extends JsonValue | null>(area: StorageArea, key: string, ttlMs: number, validate: Validator<T>): TtlStorageEntry<T> | null;
export function readTtlStorageEntry<T extends JsonValue | null>(area: StorageArea, key: string, ttlMs: number, validate?: Validator<T>): TtlStorageEntry<JsonValue | null> | TtlStorageEntry<T> | null {
    const parsed = readStorageJson(area, key);
    if (!isTtlStorageEntry(parsed)) return null;
    const entry = parsed;
    if (ttlMs >= 0 && Date.now() - entry.timestamp > ttlMs) return null;
    const value = entry['value'];
    if (validate) {
        if (!validate(value)) return null;
        return { value, timestamp: entry.timestamp };
    }
    return { value, timestamp: entry.timestamp };
}

export function readTtlStorageValue(area: StorageArea, key: string, ttlMs: number): JsonValue | null;
export function readTtlStorageValue<T extends JsonValue | null>(area: StorageArea, key: string, ttlMs: number, validate: Validator<T>): T | null;
export function readTtlStorageValue<T extends JsonValue | null>(area: StorageArea, key: string, ttlMs: number, validate?: Validator<T>): JsonValue | T | null {
    if (validate) {
        const entry = readTtlStorageEntry(area, key, ttlMs, validate);
        return entry ? entry.value : null;
    }
    const entry = readTtlStorageEntry(area, key, ttlMs);
    return entry ? entry.value : null;
}

export const writeTtlStorageValue = <T extends JsonValue | null>(area: StorageArea, key: string, value: T): boolean => writeStorageJson(area, key, { value, timestamp: Date.now() });

type TtlCacheEntry<T> = {
    value: T;
    timestamp: number;
};

export const createTtlCache = <T>(ttlMs: number): Readonly<{ get(key: string): T | null; set(key: string, value: T): void; delete(key: string): void; clear(): void }> => {
    const cache = new Map<string, TtlCacheEntry<T>>();

    return Object.freeze({
        get(key: string): T | null {
            const entry = cache.get(key);
            if (!entry) return null;
            if (ttlMs >= 0 && Date.now() - entry.timestamp > ttlMs) {
                cache.delete(key);
                return null;
            }
            return entry.value;
        },
        set(key: string, value: T): void {
            cache.set(key, { value, timestamp: Date.now() });
        },
        delete(key: string): void {
            cache.delete(key);
        },
        clear(): void {
            cache.clear();
        }
    });
};
