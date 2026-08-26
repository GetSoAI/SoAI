/* SoAI - Shared payload readers for chat tool activity rendering [frontend/assets/ts/features/chat/toolactivity/payloadReaders.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { hasOwn, isString } from '@core/typeGuards.ts';
import { optionalTrimmedString } from '@core/types/payloadValueReaders.ts';
import { compactQueryWhitespace, parseToolActivityQueryPayload } from '@features/chat/toolactivity/payloadTextParsing.ts';

const tryResolveCompactStringField = (record: JsonObject, field: string): string | null => {
    if (!hasOwn(record, field)) {
        return null;
    }
    const raw = record[field];
    if (!isString(raw)) {
        return null;
    }
    const compacted = compactQueryWhitespace(raw);
    return compacted ? compacted : null;
};

const tryResolveIntegerField = (record: JsonObject, field: string): number | null => {
    if (!hasOwn(record, field)) {
        return null;
    }
    const raw = record[field];
    if (typeof raw === 'number' && Number.isFinite(raw)) {
        return Math.max(0, Math.floor(raw));
    }
    if (!isString(raw)) {
        return null;
    }
    const trimmed = raw.trim();
    if (!/^\d+$/.test(trimmed)) {
        return null;
    }
    return Math.max(0, Math.floor(Number(trimmed)));
};

const resolveFirstCompactStringField = (record: JsonObject, fields: readonly string[]): string | null => {
    for (const field of fields) {
        const value = tryResolveCompactStringField(record, field);
        if (value) {
            return value;
        }
    }
    return null;
};

const resolveFirstIntegerField = (record: JsonObject, fields: readonly string[]): number | null => {
    for (const field of fields) {
        const value = tryResolveIntegerField(record, field);
        if (value !== null) {
            return value;
        }
    }
    return null;
};

const tryExtractWaitArguments = (payload: JsonValue | undefined): { seconds: number | null; timezone: string | null; reason: string | null } => {
    const parsed = isString(payload) ? parseToolActivityQueryPayload(payload) : payload;
    if (!isJsonObject(parsed)) {
        return { seconds: null, timezone: null, reason: null };
    }
    const rawSeconds = parsed['seconds'];
    const rawTimezone = parsed['timezone'];
    const seconds = typeof rawSeconds === 'number' && Number.isFinite(rawSeconds) ? Math.max(0, rawSeconds) : null;
    const timezone = optionalTrimmedString(rawTimezone);
    const reason = tryResolveCompactStringField(parsed, 'reason');
    return { seconds, timezone, reason };
};

const tryExtractRecord = (payload: JsonValue | undefined): JsonObject | null => {
    if (isJsonObject(payload)) {
        if (Object.keys(payload).length === 0) {
            return null;
        }
        return payload;
    }
    if (isString(payload)) {
        const trimmed = payload.trim();
        if (!trimmed.startsWith('{')) {
            return null;
        }
        const parsed = parseToolActivityQueryPayload(trimmed);
        if (isJsonObject(parsed) && Object.keys(parsed).length > 0) {
            return parsed;
        }
        return null;
    }
    return null;
};

const resolvePayloadRecord = (payload: JsonValue | undefined): JsonObject | null => {
    if (isString(payload)) {
        const trimmed = payload.trim();
        if (!trimmed) {
            return null;
        }
        const parsed = parseToolActivityQueryPayload(trimmed);
        if (isString(parsed)) {
            return { query: parsed };
        }
        return tryExtractRecord(parsed);
    }
    return tryExtractRecord(payload);
};

export { resolveFirstCompactStringField, resolveFirstIntegerField, resolvePayloadRecord, tryExtractRecord, tryExtractWaitArguments, tryResolveCompactStringField, tryResolveIntegerField };
