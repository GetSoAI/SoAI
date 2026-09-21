/* SoAI - Shared serialization JSON [frontend/assets/ts/core/serialization/json.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isJsonArray, isJsonObject, isJsonValue, type JsonArray, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';

interface SafeJsonStringifyOptions {
    indent?: number;
    maxDepth?: number;
    maxArrayLength?: number;
    maxObjectKeys?: number;
    maxStringLength?: number;
}

const DEFAULT_OPTIONS: Required<SafeJsonStringifyOptions> = {
    indent: 2,
    maxDepth: 12,
    maxArrayLength: 200,
    maxObjectKeys: 200,
    maxStringLength: 10_000
};

const createReferenceStack = () => new WeakSet();

const normalizeString = (value: string, maxLength: number): string => {
    if (value.length <= maxLength) return value;
    return value.slice(0, maxLength);
};

const normalizeJsonValue = <T>(value: T, depth: number, options: Required<SafeJsonStringifyOptions>, stack: ReturnType<typeof createReferenceStack>): JsonValue => {
    if (depth > options.maxDepth) {
        return null;
    }
    if (value === null || value === undefined) {
        return null;
    }
    if (typeof value === 'string') {
        return normalizeString(value, options.maxStringLength);
    }
    if (typeof value === 'number') {
        return Number.isFinite(value) ? value : null;
    }
    if (typeof value === 'boolean') {
        return value;
    }
    if (typeof value === 'bigint') {
        return value.toString();
    }
    if (Array.isArray(value)) {
        const target = value;
        if (stack.has(target)) {
            return null;
        }
        stack.add(target);
        try {
            const normalized: JsonValue[] = [];
            const limit = Math.min(value.length, options.maxArrayLength);
            for (let index = 0; index < limit; index += 1) {
                normalized.push(normalizeJsonValue(value[index], depth + 1, options, stack));
            }
            return normalized;
        } finally {
            stack.delete(target);
        }
    }
    if (typeof value === 'object') {
        const target = value;
        if (stack.has(target)) {
            return null;
        }
        stack.add(target);
        try {
            const normalized: Record<string, JsonValue> = {};
            const entries = Object.entries(target);
            const limit = Math.min(entries.length, options.maxObjectKeys);
            for (const [key, entryValue] of entries.slice(0, limit)) {
                normalized[key] = normalizeJsonValue(entryValue, depth + 1, options, stack);
            }
            return normalized;
        } finally {
            stack.delete(target);
        }
    }
    return null;
};

const safeJsonStringify = <T>(value: T, options: SafeJsonStringifyOptions = {}): string => {
    const resolved: Required<SafeJsonStringifyOptions> = { ...DEFAULT_OPTIONS, ...options };
    const normalized = normalizeJsonValue(value, 0, resolved, createReferenceStack());
    return JSON.stringify(normalized, null, resolved.indent);
};

const stableJsonStringifyInternal = <T>(value: T, stack: ReturnType<typeof createReferenceStack>): string => {
    if (value === null || value === undefined) {
        return 'null';
    }
    if (typeof value === 'string') {
        return JSON.stringify(value);
    }
    if (typeof value === 'number') {
        return Number.isFinite(value) ? JSON.stringify(value) : 'null';
    }
    if (typeof value === 'boolean') {
        return JSON.stringify(value);
    }
    if (typeof value === 'bigint') {
        return JSON.stringify(value.toString());
    }
    if (Array.isArray(value)) {
        const target = value;
        if (stack.has(target)) {
            return 'null';
        }
        stack.add(target);
        try {
            const entries: string[] = [];
            for (let index = 0; index < value.length; index += 1) {
                entries.push(stableJsonStringifyInternal(value[index], stack));
            }
            return `[${entries.join(',')}]`;
        } finally {
            stack.delete(target);
        }
    }
    if (typeof value === 'object') {
        const target = value;
        if (stack.has(target)) {
            return 'null';
        }
        stack.add(target);
        try {
            return `{${Object.entries(value)
                .sort(([leftKey], [rightKey]) => (leftKey < rightKey ? -1 : 1))
                .map(([key, entryValue]) => `${JSON.stringify(key)}:${stableJsonStringifyInternal(entryValue, stack)}`)
                .join(',')}}`;
        } finally {
            stack.delete(target);
        }
    }
    return 'null';
};

const stableJsonStringify = <T>(value: T): string => {
    return stableJsonStringifyInternal(value, createReferenceStack());
};

const prettyJsonStringify = (value: JsonValue): string => {
    return JSON.stringify(value, null, 2);
};

const parseJsonValueText = (value: string): JsonValue => {
    const parsed = JSON.parse(value);
    if (!isJsonValue(parsed)) {
        throw new Error('Parsed JSON must contain only finite JSON values');
    }
    return parsed;
};

const parseJsonObjectText = (value: string, errorMessage: string): JsonObject | null => {
    const normalized = value.trim();
    if (!normalized) {
        return null;
    }
    try {
        const parsed = parseJsonValueText(normalized);
        if (!isJsonObject(parsed)) {
            throw new Error('JSON object required');
        }
        const objectCopy: JsonObject = {};
        Object.entries(parsed).forEach(([key, entry]) => {
            objectCopy[key] = entry;
        });
        return objectCopy;
    } catch (error) {
        throw new Error(errorMessage, { cause: ensureError(error) });
    }
};

const parseRequiredJsonText = (value: string): JsonValue => {
    return parseJsonValueText(value.trim());
};

const parseRequiredJsonObjectText = (value: string, errorMessage: string): JsonObject => {
    const parsed = parseJsonObjectText(value, errorMessage);
    if (parsed === null) {
        throw new Error(errorMessage);
    }
    return parsed;
};

const parseOptionalJsonObjectText = (value: string, errorMessage: string): JsonObject | null => parseJsonObjectText(value, errorMessage);

const parseOptionalJsonArrayText = (value: string, errorMessage: string): JsonArray | null => {
    const normalized = value.trim();
    if (!normalized) {
        return null;
    }
    try {
        const parsed = parseJsonValueText(normalized);
        if (!isJsonArray(parsed)) {
            throw new Error('JSON array required');
        }
        return parsed;
    } catch (error) {
        throw new Error(errorMessage, { cause: ensureError(error) });
    }
};

const parseOptionalJsonStringArrayText = (value: string, errorMessage: string): string[] | null => {
    const parsed = parseOptionalJsonArrayText(value, errorMessage);
    if (parsed === null) {
        return null;
    }
    if (parsed.some((entry) => !isString(entry))) {
        throw new Error('Array values must be strings');
    }
    return parsed.map((entry) => String(entry));
};

const parseOptionalJsonScalarRecordText = (value: string, errorMessage: string): Record<string, string> | null => {
    const parsed = parseOptionalJsonObjectText(value, errorMessage);
    if (parsed === null) {
        return null;
    }
    const normalized: Record<string, string> = {};
    Object.entries(parsed).forEach(([key, entry]) => {
        if (!key) {
            throw new Error('Object keys must not be empty');
        }
        if (isString(entry)) {
            normalized[key] = entry;
            return;
        }
        if (entry === null || entry === undefined) {
            throw new Error('Object values must not be null');
        }
        if (typeof entry === 'boolean') {
            normalized[key] = entry ? 'true' : 'false';
            return;
        }
        if (typeof entry === 'number' && Number.isFinite(entry)) {
            normalized[key] = String(entry);
            return;
        }
        throw new Error('Object values must be strings or scalar values');
    });
    return normalized;
};

const parseOptionalJsonStringRecordText = (value: string, errorMessage: string): Record<string, string> | null => {
    const parsed = parseOptionalJsonObjectText(value, errorMessage);
    if (parsed === null) {
        return null;
    }
    const normalized: Record<string, string> = {};
    Object.entries(parsed).forEach(([key, entry]) => {
        if (!key || !isString(entry)) {
            throw new Error(errorMessage);
        }
        normalized[key] = entry;
    });
    return normalized;
};

const parseJsonTextOrString = (value: string): JsonValue => {
    try {
        return parseJsonValueText(value);
    } catch (error) {
        errorHandler.debug('SerializationJson', 'JSON text parsing fell back to raw string', ensureError(error));
        return value;
    }
};

const tryParseJsonText = (value: string): JsonValue | null => {
    try {
        return parseJsonValueText(value.trim());
    } catch (error) {
        errorHandler.debug('SerializationJson', 'Failed to parse optional JSON text', ensureError(error));
        return null;
    }
};

export { parseJsonObjectText, parseJsonTextOrString, parseOptionalJsonArrayText, parseOptionalJsonObjectText, parseOptionalJsonScalarRecordText, parseOptionalJsonStringArrayText, parseOptionalJsonStringRecordText, parseRequiredJsonObjectText, parseRequiredJsonText, prettyJsonStringify, safeJsonStringify, stableJsonStringify, tryParseJsonText };
export type { SafeJsonStringifyOptions };
