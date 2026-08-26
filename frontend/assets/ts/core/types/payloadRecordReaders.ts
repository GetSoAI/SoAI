/* SoAI - Shared types payload record readers [frontend/assets/ts/core/types/payloadRecordReaders.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isBoolean, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const requireRecord = <T>(value: T, label: string): JsonObject => {
    if (!isJsonObject(value)) {
        throw new Error(`${label} must be an object.`);
    }
    return value;
};

const assertExactRecordKeys = (record: JsonObject, expectedKeys: readonly string[], label: string): void => {
    const expected = new Set(expectedKeys);
    const actualKeys = Object.keys(record);
    if (actualKeys.length !== expected.size || actualKeys.some((key) => !expected.has(key))) {
        throw new Error(`${label} contains an invalid field set.`);
    }
};

const readNullableStringRecordValue = <T>(value: T, label: string): Record<string, string> | null => {
    if (value === null || value === undefined) {
        return null;
    }
    const record = requireRecord(value, label);
    const normalized: Record<string, string> = {};
    Object.entries(record).forEach(([key, entry]) => {
        if (!isString(entry)) {
            throw new Error(`${label}.${key} must be a string.`);
        }
        normalized[key] = entry;
    });
    return normalized;
};

const readNullableTrimmedStringRecordValue = <T>(value: T, label: string): Record<string, string> | null => {
    if (value === null || value === undefined) {
        return null;
    }
    const record = requireRecord(value, label);
    const normalized: Record<string, string> = {};
    Object.entries(record).forEach(([key, entry]) => {
        if (!isString(entry)) {
            throw new Error(`${label}.${key} must be a string.`);
        }
        const item = entry.trim();
        if (!item) {
            throw new Error(`${label}.${key} must be a non-empty string.`);
        }
        normalized[key] = item;
    });
    return normalized;
};

const readNullableJsonObjectValue = <T>(value: T, label: string): JsonObject | null => {
    if (value === null || value === undefined) {
        return null;
    }
    return requireRecord(value, label);
};

const readRequiredBooleanRecordValue = <T>(value: T, label: string): Record<string, boolean> => {
    const record = requireRecord(value, label);
    const normalized: Record<string, boolean> = {};
    Object.entries(record).forEach(([key, entry]) => {
        if (!isBoolean(entry)) {
            throw new Error(`${label}.${key} must be a boolean.`);
        }
        normalized[key] = entry;
    });
    return normalized;
};

const readJsonObjectArrayEntries = (value: readonly JsonValue[], label: string): JsonObject[] => {
    const normalized: JsonObject[] = [];
    value.forEach((entry, index) => {
        if (!isJsonObject(entry)) {
            throw new Error(`${label}[${String(index)}] must be an object.`);
        }
        normalized.push(entry);
    });
    return normalized;
};

const readJsonObjectArrayOrEmptyValue = <T>(value: T, label: string): JsonObject[] => {
    if (value === null || value === undefined) {
        return [];
    }
    if (!Array.isArray(value)) {
        throw new Error(`${label} must be an array.`);
    }
    return readJsonObjectArrayEntries(value, label);
};

const filterJsonObjectArrayValue = <T>(value: T): JsonObject[] => {
    if (!Array.isArray(value)) {
        return [];
    }
    return value.filter(isJsonObject);
};

const readRequiredJsonObjectArrayValue = <T>(value: T, label: string): JsonObject[] => {
    if (!Array.isArray(value)) {
        throw new Error(`${label} must be an array.`);
    }
    return readJsonObjectArrayEntries(value, label);
};

export { assertExactRecordKeys, filterJsonObjectArrayValue, readJsonObjectArrayOrEmptyValue, readNullableJsonObjectValue, readNullableStringRecordValue, readNullableTrimmedStringRecordValue, readRequiredBooleanRecordValue, readRequiredJsonObjectArrayValue, requireRecord };
