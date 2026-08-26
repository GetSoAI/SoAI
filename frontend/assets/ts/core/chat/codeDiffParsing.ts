/* SoAI - Chat tool code-diff parsing and normalization [frontend/assets/ts/core/chat/codeDiffParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { tryParseJsonText } from '@core/serialization/json.ts';
import { isBoolean, isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface ToolActivityCodeDiff {
    path: string;
    operation: string;
    diff: string;
    truncated: boolean;
}

const VALID_CODE_DIFF_OPERATIONS: ReadonlySet<string> = new Set<string>(['added', 'deleted', 'updated', 'viewed']);

const normalizeOperation = (value: JsonValue | undefined): string => {
    if (!isString(value)) {
        return 'updated';
    }
    const normalized = value.trim().toLowerCase();
    return VALID_CODE_DIFF_OPERATIONS.has(normalized) ? normalized : 'updated';
};

const parseCodeDiffEntryStrict = (value: JsonValue | undefined): ToolActivityCodeDiff | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    const pathValue = value['path'];
    const diffValue = value['diff'];
    if (!isString(pathValue) || !pathValue.trim()) {
        return null;
    }
    if (!isString(diffValue) || !diffValue.trim()) {
        return null;
    }
    const truncatedValue = value['truncated'];
    if (!isBoolean(truncatedValue)) {
        return null;
    }
    return {
        path: pathValue.trim(),
        operation: normalizeOperation(value['operation']),
        diff: diffValue,
        truncated: truncatedValue
    };
};

const parseCodeDiffEntryLenient = (value: JsonValue | undefined): ToolActivityCodeDiff | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    const pathValue = value['path'];
    const diffValue = value['diff'];
    if (!isString(pathValue) || !pathValue.trim()) {
        return null;
    }
    if (!isString(diffValue) || !diffValue) {
        return null;
    }
    return {
        path: pathValue.trim(),
        operation: normalizeOperation(value['operation']),
        diff: diffValue,
        truncated: value['truncated'] === true
    };
};

const parseCodeDiffArrayStrict = (value: JsonValue | undefined): ToolActivityCodeDiff[] | null => {
    if (!isJsonArray(value)) {
        return null;
    }
    const normalized: ToolActivityCodeDiff[] = [];
    for (const entry of value) {
        const parsed = parseCodeDiffEntryStrict(entry);
        if (parsed === null) {
            return null;
        }
        normalized.push(parsed);
    }
    return normalized;
};

const parseCodeDiffArrayLenient = (value: JsonValue | undefined): ToolActivityCodeDiff[] | null => {
    if (!isJsonArray(value)) {
        return null;
    }
    const normalized: ToolActivityCodeDiff[] = [];
    for (const entry of value) {
        const parsed = parseCodeDiffEntryLenient(entry);
        if (parsed) {
            normalized.push(parsed);
        }
    }
    return normalized.length > 0 ? normalized : null;
};

const parseOptionalCodeDiffArrayStrict = (value: JsonValue | undefined): ToolActivityCodeDiff[] | null | undefined => {
    if (value === undefined) {
        return undefined;
    }
    return parseCodeDiffArrayStrict(value);
};

const parseToolResultPayload = (value: JsonValue | undefined): JsonValue | undefined | null => {
    if (!isString(value)) {
        return null;
    }
    const trimmed = value.trim();
    if (!trimmed || (!trimmed.startsWith('{') && !trimmed.startsWith('['))) {
        return null;
    }
    return tryParseJsonText(trimmed);
};

const resolveCodeDiffsFromToolResult = (result: JsonValue | undefined): ToolActivityCodeDiff[] | null => {
    if (result === undefined || result === null) {
        return null;
    }
    const payload = isJsonObject(result) ? result : parseToolResultPayload(result);
    if (!payload || !isJsonObject(payload)) {
        return null;
    }
    const candidate = payload['code_diffs'];
    const diffs = parseCodeDiffArrayLenient(candidate);
    return diffs;
};

export { parseCodeDiffArrayLenient, parseOptionalCodeDiffArrayStrict, resolveCodeDiffsFromToolResult };
export type { ToolActivityCodeDiff };
