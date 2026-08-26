/* SoAI - Shared frontend storage service adapters [frontend/assets/ts/core/storage/service/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { getStructuredClone, getWindow } from '@core/environment/public.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { LOG_LINE_LIMITS } from '@core/storage/namespaces.ts';
import type { StorageAdapters, StorageRuntimeState } from '@core/storage/service/types.ts';
import type { StorageType } from '@core/storage/types.ts';
import { isJsonObject, isJsonValue, type JsonArray, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const createStorageAdapters = (state: StorageRuntimeState): StorageAdapters => {
    const cloneFunction = getStructuredClone();

    const clone = <T>(value: T): T => {
        return value === null || typeof value !== 'object' ? value : cloneFunction(value);
    };

    const checkStorage = (storage: Storage): boolean => {
        if (!storage) {
            throw new Error('Storage APIs are unavailable');
        }
        const testKey = 'soai.storage.test';
        storage.setItem(testKey, '1');
        storage.removeItem(testKey);
        return true;
    };

    const initializeStorageAvailability = (): void => {
        const win = getWindow();
        state.localStorageAvailable = checkStorage(win.localStorage);
        state.sessionStorageAvailable = checkStorage(win.sessionStorage);
    };

    const readFromStorage = (storage: Storage, key: string): JsonValue | null => {
        try {
            const raw = storage.getItem(key);
            if (!raw) return null;
            const parsed = parseRequiredJsonText(raw);
            if (!isJsonValue(parsed)) {
                throw new TypeError(`Storage key ${key} must contain JSON`);
            }
            return parsed;
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('StorageManager', `Failed to parse storage key: ${key}`, runtimeError);
            throw ensureError(error);
        }
    };

    const writeToStorage = (storage: Storage, key: string, value: JsonValue | null | undefined): void => {
        if (value === null || value === undefined) {
            storage.removeItem(key);
            return;
        }
        if (typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 0) {
            storage.removeItem(key);
            return;
        }
        storage.setItem(key, JSON.stringify(value));
    };

    const readStorage = (storageType: StorageType, key: string): JsonValue | null => {
        const win = getWindow();
        if (storageType === 'localStorage') {
            if (!state.localStorageAvailable) {
                return null;
            }
            return readFromStorage(win.localStorage, key);
        }
        if (!state.sessionStorageAvailable) {
            return null;
        }
        return readFromStorage(win.sessionStorage, key);
    };

    const writeStorage = (storageType: StorageType, key: string, value: JsonValue | null | undefined): void => {
        const win = getWindow();
        if (storageType === 'localStorage') {
            if (state.localStorageAvailable) {
                writeToStorage(win.localStorage, key, value);
            }
            return;
        }
        if (state.sessionStorageAvailable) {
            writeToStorage(win.sessionStorage, key, value);
        }
    };

    const normalizeLimit = (limit: number): number => {
        const normalized = Number(limit);
        if (!LOG_LINE_LIMITS.includes(normalized)) {
            throw new RangeError(`Log line limit ${normalized} is not supported.`);
        }
        return normalized;
    };

    const normalizeZoom = (zoom: number, min: number, max: number): number => {
        const normalized = Number(zoom);
        if (normalized < min || normalized > max) {
            throw new RangeError(`Text zoom ${normalized} is outside range`);
        }
        return normalized;
    };

    const serialize = (value: JsonValue | null | undefined): string => {
        const seen = new WeakSet<JsonObject | JsonArray>();
        const normalize = (input: JsonValue | null | undefined): JsonValue | null => {
            if (input === undefined) {
                return null;
            }
            if (Array.isArray(input)) {
                if (seen.has(input)) {
                    throw new TypeError('Cannot serialize circular structure');
                }
                seen.add(input);
                const normalized = input.map(normalize);
                seen.delete(input);
                return normalized;
            }
            if (isJsonObject(input)) {
                if (seen.has(input)) {
                    throw new TypeError('Cannot serialize circular structure');
                }
                seen.add(input);
                const out: JsonObject = {};
                for (const key of Object.keys(input).sort((left, right) => left.localeCompare(right, 'en'))) {
                    out[key] = normalize(input[key]);
                }
                seen.delete(input);
                return out;
            }
            return input;
        };
        const serialized = JSON.stringify(normalize(value));
        return serialized === undefined ? 'undefined' : serialized;
    };

    return {
        clone,
        initializeStorageAvailability,
        readStorage,
        writeStorage,
        normalizeLimit,
        normalizeZoom,
        serialize
    };
};

export { createStorageAdapters };
export type { StorageAdapters };
