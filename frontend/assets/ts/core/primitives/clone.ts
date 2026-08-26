/* SoAI - Shared primitives clone [frontend/assets/ts/core/primitives/clone.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, type Constructor } from '@core/typeGuards.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { isJsonArray, isJsonObject, isJsonValue, type JsonArray, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

type ClonePassthroughValue = Event;

export interface CloneOptions {
    passthroughTypes?: Constructor<ClonePassthroughValue>[];
}

const resolveStructuredClone = (): typeof structuredClone => {
    const clone = globalThis.structuredClone;
    if (!isFunction(clone)) throw new Error('Structured clone is unavailable');
    return clone;
};

export const cloneStructured = <T>(value: T, options: CloneOptions = {}): T => {
    if (value === null || value === undefined || typeof value !== 'object') return value;
    const passthroughTypes = options.passthroughTypes;
    if (Array.isArray(passthroughTypes)) {
        for (const type of passthroughTypes) {
            if (isFunction(type) && value instanceof type) return value;
        }
    }
    return resolveStructuredClone()(value);
};

export const cloneJsonValue = (value: JsonValue): JsonValue => {
    const cloned = resolveStructuredClone()(value);
    if (!isJsonValue(cloned)) throw new Error('Structured JSON clone produced a non-JSON value');
    return cloned;
};

export const cloneJsonObject = (value: JsonObject): JsonObject => {
    const cloned = cloneJsonValue(value);
    if (!isJsonObject(cloned)) throw new Error('Structured JSON object clone produced a non-object value');
    return cloned;
};

export const cloneJsonArray = (value: JsonArray): JsonArray => {
    const cloned = cloneJsonValue(value);
    if (!isJsonArray(cloned)) throw new Error('Structured JSON array clone produced a non-array value');
    return cloned;
};

export const toJsonCompatibleValue = <T>(value: T): JsonValue => {
    const serialized = JSON.stringify(value);
    return serialized === undefined ? null : parseRequiredJsonText(serialized);
};

export const toJsonCompatibleObject = <T>(value: T): JsonObject => {
    const normalized = toJsonCompatibleValue(value);
    if (!isJsonObject(normalized)) {
        throw new Error('Value could not be normalized to a JSON object.');
    }
    return normalized;
};

export const deepClone = <T>(object: T, options?: CloneOptions): T => cloneStructured(object, options);
