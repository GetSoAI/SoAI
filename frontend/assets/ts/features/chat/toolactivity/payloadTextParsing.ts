/* SoAI - DOM-free parsing helpers for tool activity payloads [frontend/assets/ts/features/chat/toolactivity/payloadTextParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { tryParseJsonText } from '@core/serialization/json.ts';
import { hasOwn, isString } from '@core/typeGuards.ts';
import { parseSsePayload } from '@features/chat/toolactivity/ssePayloadParsing.ts';

type ToolActivityQueryField = { key: string; value: string };

type ToolActivityQueryModel = { primary: string; fields: ToolActivityQueryField[] };

const TOOL_QUERY_PRIMARY_KEYS = ['task', 'command', 'query', 'prompt', 'url', 'file_path', 'path', 'pattern'];

const isCompleteJsonPayloadText = (payload: string): boolean => {
    const trimmedPayload = payload.trim();
    if (!trimmedPayload) {
        return false;
    }
    const firstCharacter = trimmedPayload.charAt(0);
    if (firstCharacter !== '{' && firstCharacter !== '[') {
        return false;
    }
    const expectedClose = firstCharacter === '{' ? '}' : ']';
    const stack: string[] = [firstCharacter];
    let inString = false;
    let escaped = false;
    for (let index = 1; index < trimmedPayload.length; index += 1) {
        const character = trimmedPayload.charAt(index);
        if (inString) {
            if (escaped) {
                escaped = false;
                continue;
            }
            if (character === '\\\\') {
                escaped = true;
                continue;
            }
            if (character === '"') {
                inString = false;
            }
            continue;
        }
        if (character === '"') {
            inString = true;
            continue;
        }
        if (character === '{' || character === '[') {
            stack.push(character);
            continue;
        }
        if (character === '}' || character === ']') {
            if (stack.length === 0) {
                return false;
            }
            const open = stack[stack.length - 1];
            if (!open) {
                return false;
            }
            const isMatch = (open === '{' && character === '}') || (open === '[' && character === ']');
            if (!isMatch) {
                return false;
            }
            stack.pop();
        }
    }
    if (inString || stack.length !== 0) {
        return false;
    }
    let lastNonWhitespaceIndex = trimmedPayload.length - 1;
    while (lastNonWhitespaceIndex >= 0 && /\s/.test(trimmedPayload.charAt(lastNonWhitespaceIndex))) {
        lastNonWhitespaceIndex -= 1;
    }
    if (lastNonWhitespaceIndex < 0) {
        return false;
    }
    return trimmedPayload.charAt(lastNonWhitespaceIndex) === expectedClose;
};

const compactQueryWhitespace = (value: string): string => value.replace(/\s+/g, ' ').trim();

const clampQueryValue = (value: string, maxLength: number): string => (value.length > maxLength ? `${value.slice(0, maxLength - 3)}...` : value);

const clampToolHeaderPreview = (value: string): string => clampQueryValue(value, 280);

const normalizeQueryValue = (value: JsonValue | undefined): string | null => {
    if (value === null || value === undefined) {
        return null;
    }
    if (isString(value)) {
        const compacted = compactQueryWhitespace(value);
        return compacted ? compacted : null;
    }
    if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
        return String(value);
    }
    if (isJsonArray(value)) {
        const compactValues = value
            .map((entry) => normalizeQueryValue(entry))
            .filter((entry): entry is string => entry !== null)
            .slice(0, 3);
        if (compactValues.length === 0) {
            return null;
        }
        return compactValues.join(', ');
    }
    return null;
};

const resolveQueryFromRecord = (payload: JsonObject): ToolActivityQueryModel | null => {
    const entries = Object.entries(payload);
    if (entries.length === 0) {
        return null;
    }

    let primaryValue = '';
    let primaryKey = '';

    for (const candidateKey of TOOL_QUERY_PRIMARY_KEYS) {
        if (!hasOwn(payload, candidateKey)) {
            continue;
        }
        const candidateValue = normalizeQueryValue(payload[candidateKey]);
        if (!candidateValue) {
            continue;
        }
        primaryValue = candidateValue;
        primaryKey = candidateKey;
        break;
    }

    if (!primaryValue) {
        for (const [entryKey, entryValue] of entries) {
            const candidateValue = normalizeQueryValue(entryValue);
            if (!candidateValue) {
                continue;
            }
            primaryValue = candidateValue;
            primaryKey = entryKey;
            break;
        }
    }

    if (!primaryValue) {
        return null;
    }

    const fields: ToolActivityQueryField[] = [];
    for (const [entryKey, entryValue] of entries) {
        if (entryKey === primaryKey) {
            continue;
        }
        const normalizedValue = normalizeQueryValue(entryValue);
        if (!normalizedValue) {
            continue;
        }
        fields.push({ key: entryKey.replace(/_/g, ' '), value: clampQueryValue(normalizedValue, 120) });
    }

    return {
        primary: clampQueryValue(primaryValue, 280),
        fields
    };
};

const parseToolActivityQueryPayload = (payload: string): JsonValue => {
    const trimmedPayload = payload.trim();
    if (!trimmedPayload) {
        return '';
    }

    const sseParsed = parseSsePayload(trimmedPayload);
    if (sseParsed !== null) {
        if (sseParsed.length === 1) {
            const first = sseParsed[0];
            return first === undefined ? '' : first;
        }
        return sseParsed;
    }

    const startsWithJson = trimmedPayload.startsWith('{') || trimmedPayload.startsWith('[');
    if (!startsWithJson) {
        return trimmedPayload;
    }
    if (!isCompleteJsonPayloadText(trimmedPayload)) {
        return '';
    }
    return tryParseJsonText(trimmedPayload) ?? trimmedPayload;
};

const resolveToolActivityQueryModel = (payload: JsonValue | undefined): ToolActivityQueryModel | null => {
    const resolved = isString(payload) ? parseToolActivityQueryPayload(payload) : payload;
    if (isString(resolved)) {
        const compacted = compactQueryWhitespace(resolved);
        if (!compacted) {
            return null;
        }
        return { primary: clampQueryValue(compacted, 280), fields: [] };
    }
    if (isJsonArray(resolved)) {
        const compactValues = resolved
            .map((entry) => normalizeQueryValue(entry))
            .filter((entry): entry is string => entry !== null)
            .slice(0, 3);
        if (compactValues.length === 0) {
            return null;
        }
        return { primary: clampQueryValue(compactValues.join(', '), 280), fields: [] };
    }
    if (isJsonObject(resolved)) {
        return resolveQueryFromRecord(resolved);
    }
    const normalized = normalizeQueryValue(resolved);
    return normalized ? { primary: clampQueryValue(normalized, 280), fields: [] } : null;
};

export { clampToolHeaderPreview, compactQueryWhitespace, isCompleteJsonPayloadText, parseToolActivityQueryPayload, resolveToolActivityQueryModel };
export type { ToolActivityQueryModel };
