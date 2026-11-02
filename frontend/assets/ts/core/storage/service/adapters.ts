/* SoAI - Shared frontend storage service adapters [frontend/assets/ts/core/storage/service/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { getStructuredClone, getWindow } from '@core/environment/public.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { LOG_LINE_LIMITS } from '@core/storage/namespaces.ts';
import type { StorageAdapters, StorageRuntimeState, OptionalStorageRead, OptionalStorageMutation } from '@core/storage/service/types.ts';
import type { StorageType } from '@core/storage/types.ts';
import { isJsonObject, isJsonValue, type JsonArray, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const createStorageAdapters = (state: Pick<StorageRuntimeState, 'localStorageAvailable' | 'sessionStorageAvailable'>): StorageAdapters => {
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

    const resolveOptionalStorage = (storageType: StorageType): Storage | null => {
        const available = storageType === 'localStorage' ? state.localStorageAvailable : state.sessionStorageAvailable;
        if (!available) return null;
        const win = getWindow();
        return storageType === 'localStorage' ? win.localStorage : win.sessionStorage;
    };

    const requireRecordLimit = (maximumLength: number): void => {
        if (!Number.isSafeInteger(maximumLength) || maximumLength < 1) throw new RangeError('Optional storage records require a positive finite size limit');
    };

    const readOptionalRecord = (storageType: StorageType, key: string, maximumLength: number): OptionalStorageRead => {
        requireRecordLimit(maximumLength);
        let raw: string | null;
        try {
            const storage = resolveOptionalStorage(storageType);
            if (!storage) return { type: 'unavailable', error: null };
            raw = storage.getItem(key);
        } catch (error) {
            return { type: 'unavailable', error: ensureError(error) };
        }
        if (raw === null) return { type: 'missing' };
        if (raw.length > maximumLength) return { type: 'invalid', reason: 'size', rawText: raw };
        try {
            const value = parseRequiredJsonText(raw);
            return isJsonValue(value) ? { type: 'value', value } : { type: 'invalid', reason: 'content' };
        } catch {
            return { type: 'invalid', reason: 'content' };
        }
    };

    const mutateOptionalRecord = (storageType: StorageType, key: string, mutation: { type: 'write'; serialized: string } | { type: 'remove' }, canMutate: () => boolean): OptionalStorageMutation => {
        let storage: Storage | null;
        try {
            storage = resolveOptionalStorage(storageType);
        } catch (error) {
            return { type: 'unavailable', error: ensureError(error) };
        }
        if (!storage) return { type: 'unavailable', error: null };
        if (!canMutate()) return { type: 'superseded' };
        try {
            if (mutation.type === 'remove') {
                storage.removeItem(key);
                return { type: 'removed' };
            }
            storage.setItem(key, mutation.serialized);
            return { type: 'written' };
        } catch (error) {
            return { type: 'unavailable', error: ensureError(error) };
        }
    };

    const writeOptionalRecord = (storageType: StorageType, key: string, value: JsonValue, maximumLength: number, canMutate: () => boolean): OptionalStorageMutation => {
        requireRecordLimit(maximumLength);
        let serialized: string;
        try {
            serialized = JSON.stringify(value);
        } catch {
            return { type: 'invalid', reason: 'content' };
        }
        if (serialized.length > maximumLength) return { type: 'invalid', reason: 'size' };
        return mutateOptionalRecord(storageType, key, { type: 'write', serialized }, canMutate);
    };

    const removeOptionalRecord = (storageType: StorageType, key: string, canMutate: () => boolean): OptionalStorageMutation => mutateOptionalRecord(storageType, key, { type: 'remove' }, canMutate);

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
        readOptionalRecord,
        writeOptionalRecord,
        removeOptionalRecord,
        normalizeLimit,
        normalizeZoom,
        serialize
    };
};

export { createStorageAdapters };
export type { StorageAdapters };
