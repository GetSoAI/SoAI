/* SoAI - Shared frontend MCP value normalization [frontend/assets/ts/core/mcp/valueNormalization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { requirePlainObject } from '@core/assertions.ts';
import { isArray, isNullOrUndefined, isString } from '@core/typeGuards.ts';

type OptionalJsonValue = JsonValue | undefined;

const optionalStringValue = (value: OptionalJsonValue, label: string): string | null => {
    if (isNullOrUndefined(value)) {
        return null;
    }
    if (isString(value)) {
        return value;
    }
    throw new Error(`Invalid ${label}`);
};

const normalizeBooleanOrDefault = (value: OptionalJsonValue, defaultValue: boolean, label: string): boolean => {
    if (isNullOrUndefined(value)) {
        return defaultValue;
    }
    if (value !== true && value !== false) {
        throw new Error(`Invalid ${label}`);
    }
    return value;
};

const requireToolNameList = (value: OptionalJsonValue, label: string): string[] => {
    if (!isArray(value)) {
        throw new Error(`Invalid ${label}`);
    }
    const normalized: string[] = [];
    const seen = new Set<string>();
    for (let index = 0; index < value.length; index += 1) {
        const entry = value[index];
        if (!isString(entry)) {
            throw new Error(`Invalid ${label}`);
        }
        const trimmed = entry.trim();
        if (!trimmed) {
            throw new Error(`Invalid ${label}`);
        }
        if (seen.has(trimmed)) {
            throw new Error(`Invalid ${label}`);
        }
        seen.add(trimmed);
        normalized.push(trimmed);
    }
    return normalized;
};

const normalizeOptionalToolNameList = (value: OptionalJsonValue, label: string): string[] => {
    if (isNullOrUndefined(value)) {
        return [];
    }
    return requireToolNameList(value, label);
};

const requireBooleanRecord = (value: OptionalJsonValue, label: string): Record<string, boolean> => {
    const record = requirePlainObject(value, label, { message: `Invalid ${label}` });
    const next: Record<string, boolean> = {};
    for (const [keyRaw, value] of Object.entries(record)) {
        const key = keyRaw.trim();
        if (!key) {
            throw new Error(`Invalid ${label}`);
        }
        if (value !== true && value !== false) {
            throw new Error(`Invalid ${label}`);
        }
        next[key] = value;
    }
    return next;
};

const normalizeOptionalBooleanRecord = (value: OptionalJsonValue, label: string): Record<string, boolean> => {
    if (isNullOrUndefined(value)) {
        return {};
    }
    return requireBooleanRecord(value, label);
};

export { normalizeBooleanOrDefault, normalizeOptionalBooleanRecord, normalizeOptionalToolNameList, optionalStringValue, requireBooleanRecord, requireToolNameList };
