/* SoAI - Shared tool output presentation model [frontend/assets/ts/features/chat/toolactivity/toolOutputPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { safeJsonStringify, stableJsonStringify } from '@core/serialization/json.ts';
import { hasOwn, isNonNegativeInteger, isNumber, isString } from '@core/typeGuards.ts';
import { buildGrepFilesDisplayRecord } from '@features/chat/toolactivity/grepFilesPresentation.ts';

interface ToolResultPresentation {
    displayRecord: JsonObject | null;
    signature: string;
}

interface ToolOutputTruncation {
    totalChars: number;
    truncatedChars: number;
}

interface ToolCallOutputPresentation {
    copyText: string;
    displayRecord: JsonObject;
    hasDisplayTruncation: boolean;
    nextBeforeLiveSequence: number | null;
}

const MAX_MODAL_DISPLAY_OUTPUT_CHARS = 200_000;
const READ_FILE_TOOL_NAME = 'read_file';
const WEB_FETCH_TOOL_NAMES: ReadonlySet<string> = new Set<string>(['web_fetch', 'knowledge_web_fetch']);
const WEB_FETCH_REQUEST_DUPLICATE_KEYS: ReadonlySet<string> = new Set<string>(['url', 'extract_mode', 'max_chars']);
const WEB_FETCH_PLAIN_FALSE_KEYS: ReadonlySet<string> = new Set<string>(['persisted']);

const isWebFetchTool = (toolLeafName: string): boolean => WEB_FETCH_TOOL_NAMES.has(toolLeafName);

const truncateText = (value: string, limit: number): string => {
    const truncatedCharCount = value.length - limit;
    return truncatedCharCount <= 0 ? value : `${value.slice(0, limit)}\n\n${i18n.t('chat.toolActivity.truncatedChars', { count: String(truncatedCharCount) })}`;
};

const cloneJsonObject = (record: JsonObject): JsonObject => {
    const cloned: JsonObject = {};
    for (const [key, value] of Object.entries(record)) {
        cloned[key] = value;
    }
    return cloned;
};

const truncatePlanWriteResultPayload = (payload: JsonValue | undefined): JsonValue | undefined => {
    if (isString(payload)) {
        return truncateText(payload, 2400);
    }
    if (isJsonObject(payload)) {
        const record: JsonObject = {};
        for (const [key, value] of Object.entries(payload)) {
            if (key === 'markdown' || key === 'content') {
                continue;
            }
            record[key] = value;
        }
        return record;
    }
    return payload;
};

const scalarValuesMatch = (left: JsonValue | undefined, right: JsonValue | undefined): boolean => {
    if (typeof left === 'number' && typeof right === 'number') {
        return Number.isFinite(left) && Number.isFinite(right) && left === right;
    }
    if (typeof left === 'boolean' && typeof right === 'boolean') {
        return left === right;
    }
    const leftText = toTrimmedString(left);
    const rightText = toTrimmedString(right);
    return leftText.length > 0 && rightText.length > 0 && leftText === rightText;
};

const shouldHideExactRequestDuplicate = (key: string, value: JsonValue | undefined, requestRecord: JsonObject | null): boolean => {
    return requestRecord !== null && hasOwn(requestRecord, key) && scalarValuesMatch(value, requestRecord[key]);
};

const shouldOmitReadFileContent = (toolLeafName: string, resultRecord: JsonObject): boolean => {
    if (toolLeafName !== READ_FILE_TOOL_NAME) {
        return false;
    }
    return resultRecord['binary'] === true || resultRecord['content_omitted'] === true;
};

const shouldHideWebFetchField = (key: string, value: JsonValue | undefined, requestRecord: JsonObject | null, toolLeafName: string, consumedImageKeys: readonly string[]): boolean => {
    if (consumedImageKeys.includes(key)) {
        return true;
    }
    if (toolLeafName === 'web_fetch' && WEB_FETCH_PLAIN_FALSE_KEYS.has(key) && value === false) {
        return true;
    }
    if (key === 'final_url') {
        return requestRecord !== null && scalarValuesMatch(value, requestRecord['url']);
    }
    if (WEB_FETCH_REQUEST_DUPLICATE_KEYS.has(key)) {
        return shouldHideExactRequestDuplicate(key, value, requestRecord);
    }
    return false;
};

const buildDisplayRecord = (toolLeafName: string, resultRecord: JsonObject, requestRecord: JsonObject | null, consumedImageKeys: readonly string[]): JsonObject | null => {
    if (toolLeafName === 'grep_files') {
        return buildGrepFilesDisplayRecord(resultRecord);
    }
    const displayRecord: JsonObject = {};
    const webFetchTool = isWebFetchTool(toolLeafName);
    const omitReadFileContent = shouldOmitReadFileContent(toolLeafName, resultRecord);
    for (const [key, value] of Object.entries(resultRecord)) {
        if (omitReadFileContent && key === 'content') {
            continue;
        }
        if (webFetchTool && shouldHideWebFetchField(key, value, requestRecord, toolLeafName, consumedImageKeys)) {
            continue;
        }
        if (!webFetchTool && consumedImageKeys.includes(key)) {
            continue;
        }
        if (shouldHideExactRequestDuplicate(key, value, requestRecord)) {
            continue;
        }
        displayRecord[key] = value;
    }
    if (omitReadFileContent) {
        displayRecord['content_omitted'] = true;
        displayRecord['rendered_as_text'] = false;
    }
    return Object.keys(displayRecord).length > 0 ? displayRecord : null;
};

const resolveStringSignature = (value: string): string => {
    return stableJsonStringify(['string', value.length, value]);
};

const resolveValueSignature = (value: JsonValue | undefined): string => {
    return stableJsonStringify(['value', value]);
};

const resolvePresentationSignature = (toolLeafName: string, displayRecord: JsonObject | null): string => {
    if (displayRecord === null) {
        return `${toolLeafName}:empty`;
    }
    const entries = Object.entries(displayRecord).map(([key, value]) => `${resolveStringSignature(key)}=${resolveValueSignature(value)}`);
    return `${toolLeafName}:${entries.join('|')}`;
};

const resolveToolResultPresentation = (inputArguments: { toolLeafName: string; resultRecord: JsonObject; requestRecord: JsonObject | null; consumedImageKeys: readonly string[] }): ToolResultPresentation => {
    const displayRecord = buildDisplayRecord(inputArguments.toolLeafName, inputArguments.resultRecord, inputArguments.requestRecord, inputArguments.consumedImageKeys);
    return {
        displayRecord,
        signature: resolvePresentationSignature(inputArguments.toolLeafName, displayRecord)
    };
};

const resolveToolOutputTruncation = (payload: JsonValue | undefined): ToolOutputTruncation | null => {
    if (!isJsonObject(payload) || payload['output_is_truncated'] !== true) {
        return null;
    }
    const totalChars = payload['output_total_chars'];
    const truncatedChars = payload['output_truncated_chars'];
    if (!isNumber(totalChars) || !Number.isFinite(totalChars) || !Number.isInteger(totalChars) || totalChars <= 0) {
        return null;
    }
    if (!isNumber(truncatedChars) || !Number.isFinite(truncatedChars) || !Number.isInteger(truncatedChars) || truncatedChars <= 0) {
        return null;
    }
    return { totalChars, truncatedChars };
};

const resolveToolCallCopyText = (toolCall: JsonObject): string => {
    const result = toolCall['result'];
    const resultRecord = isJsonObject(result) ? result : null;
    const outputValue = resultRecord ? resultRecord['output'] : null;
    if (isString(outputValue)) {
        return outputValue;
    }
    if (isString(result)) {
        return result;
    }
    const errorValue = toolCall['error'];
    if (isString(errorValue) && errorValue.trim()) {
        return errorValue.trim();
    }
    return safeJsonStringify(toolCall, { indent: 2 });
};

const addToolCallSummaryField = (summary: JsonObject, toolCall: JsonObject, field: string): void => {
    const value = toolCall[field];
    if (value !== undefined) {
        summary[field] = value;
    }
};

const addToolCallResultField = (summary: JsonObject, toolCall: JsonObject): boolean => {
    const resultValue = toolCall['result'];
    if (resultValue === undefined) {
        return false;
    }
    if (!isJsonObject(resultValue)) {
        summary['result'] = resultValue;
        return false;
    }
    const output = resultValue['output'];
    if (!isString(output) || output.length <= MAX_MODAL_DISPLAY_OUTPUT_CHARS) {
        summary['result'] = resultValue;
        return false;
    }
    const nextResult = cloneJsonObject(resultValue);
    nextResult['output'] = output.slice(0, MAX_MODAL_DISPLAY_OUTPUT_CHARS);
    nextResult['output_display_is_truncated'] = true;
    nextResult['output_display_total_chars'] = output.length;
    summary['result'] = nextResult;
    return true;
};

const resolveNextBeforeLiveSequence = (toolCall: JsonObject): number | null => {
    const liveEventsPage = toolCall['liveEventsPage'];
    if (!isJsonObject(liveEventsPage)) {
        return null;
    }
    const nextBeforeLiveSequence = liveEventsPage['nextBeforeLiveSequence'];
    return isNonNegativeInteger(nextBeforeLiveSequence) ? nextBeforeLiveSequence : null;
};

const resolveToolCallOutputPresentation = (toolCall: JsonObject): ToolCallOutputPresentation => {
    const displayRecord: JsonObject = {};
    addToolCallSummaryField(displayRecord, toolCall, 'tool_name');
    addToolCallSummaryField(displayRecord, toolCall, 'status');
    const errorValue = toolCall['error'];
    if (errorValue !== undefined && errorValue !== null) {
        displayRecord['error'] = errorValue;
    }
    addToolCallSummaryField(displayRecord, toolCall, 'duration_ms');
    addToolCallSummaryField(displayRecord, toolCall, 'started_at_ms');
    addToolCallSummaryField(displayRecord, toolCall, 'arguments');
    const hasDisplayTruncation = addToolCallResultField(displayRecord, toolCall);
    addToolCallSummaryField(displayRecord, toolCall, 'liveEventsPage');
    return {
        copyText: resolveToolCallCopyText(toolCall),
        displayRecord,
        hasDisplayTruncation,
        nextBeforeLiveSequence: resolveNextBeforeLiveSequence(toolCall)
    };
};

export { resolveToolCallOutputPresentation, resolveToolOutputTruncation, resolveToolResultPresentation, truncatePlanWriteResultPayload };
export type { ToolCallOutputPresentation, ToolOutputTruncation, ToolResultPresentation };
