/* SoAI - Shared types JSON values [frontend/assets/ts/core/types/jsonValues.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type JsonPrimitive = string | number | boolean | null;

type JsonValue = JsonPrimitive | JsonArray | JsonObject;

interface JsonObject {
    [key: string]: JsonValue;
}

type JsonArray = readonly JsonValue[];

type JsonRecord = Record<string, JsonValue>;

const isJsonValue = <T>(value: T): value is T & JsonValue => {
    if (value === null) {
        return true;
    }
    if (typeof value === 'string' || typeof value === 'boolean') {
        return true;
    }
    if (typeof value === 'number') {
        return Number.isFinite(value);
    }
    if (Array.isArray(value)) {
        return value.every(isJsonValue);
    }
    if (typeof value !== 'object') {
        return false;
    }
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) {
        return false;
    }
    return Object.values(value).every(isJsonValue);
};

function isJsonArray(value: JsonValue | null | undefined): value is JsonArray;
function isJsonArray<T>(value: T): value is T & JsonArray;
function isJsonArray<T>(value: T): value is T & JsonArray {
    return Array.isArray(value) && value.every(isJsonValue);
}

function isJsonObject(value: JsonValue | null | undefined): value is JsonObject;
function isJsonObject<T>(value: T): value is T & JsonObject;
function isJsonObject<T>(value: T): value is T & JsonObject {
    return isJsonValue(value) && value !== null && typeof value === 'object' && !Array.isArray(value);
}

export { isJsonArray, isJsonObject, isJsonValue };

export type { JsonArray, JsonObject, JsonPrimitive, JsonRecord, JsonValue };
