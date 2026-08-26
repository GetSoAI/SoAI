/* SoAI - Shared types payload path reader [frontend/assets/ts/core/types/payloadPathReader.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';

const readPayloadPathValue = <T>(value: T, path: readonly string[]): JsonValue | null | undefined => {
    let current: JsonValue | undefined = isJsonValue(value) ? value : undefined;
    for (const segment of path) {
        if (!isJsonObject(current)) {
            return null;
        }
        current = current[segment];
    }
    return current;
};

const readPayloadDottedPathValue = <T>(value: T, path: string): JsonValue | undefined => {
    const segments = path.split('.').filter((segment) => segment.length > 0);
    if (segments.length === 0) {
        return isJsonValue(value) ? value : undefined;
    }
    let current: JsonValue | undefined = isJsonValue(value) ? value : undefined;
    for (const segment of segments) {
        if (!isJsonObject(current)) {
            return undefined;
        }
        current = current[segment];
    }
    return current;
};

const readJsonObjectDottedPathValueOrDefault = <T, TDefault>(value: T, path: string, defaultValue: TDefault, label: string): JsonValue | TDefault => {
    const segments = path.split('.').filter((segment) => segment.length > 0);
    let current: JsonValue | undefined = isJsonValue(value) ? value : undefined;
    for (const segment of segments) {
        if (current === null || current === undefined) {
            return defaultValue;
        }
        if (!isJsonObject(current)) {
            throw new TypeError(`${label} "${path}" expects an object at "${segment}", got ${typeof current}`);
        }
        const next = current[segment];
        if (next === undefined) {
            return defaultValue;
        }
        current = next;
    }
    return current === null || current === undefined ? defaultValue : current;
};

const readJsonObjectDottedPathValue = <T>(value: T, path: string): JsonValue | undefined => {
    const segments = path.split('.').filter((segment) => segment.length > 0);
    let current: JsonValue | undefined = isJsonValue(value) ? value : undefined;
    for (const segment of segments) {
        if (!isJsonObject(current)) {
            return undefined;
        }
        current = current[segment];
        if (current === undefined) {
            return undefined;
        }
    }
    return current;
};

export { readJsonObjectDottedPathValue, readJsonObjectDottedPathValueOrDefault, readPayloadDottedPathValue, readPayloadPathValue };
