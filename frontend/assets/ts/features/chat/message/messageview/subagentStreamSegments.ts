/* SoAI - Chat feature subagent stream segments [frontend/assets/ts/features/chat/message/messageview/subagentStreamSegments.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber, isString } from '@core/typeGuards.ts';
import { readNonNegativeIntegerOrNullValue } from '@core/types/payloadNumberReaders.ts';
import { isJsonArray, isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { resolveAnchoredAssistantSegments, type AnchoredAssistantActivity } from '@features/chat/message/anchoredAssistantSegments.ts';
import type { InlineToolActivitySegment, MessageSegment, TextSegment } from '@features/chat/message/messageSegments.ts';
import { buildSubagentChildToolSegment } from '@features/chat/message/messageview/subagentToolCallSegments.ts';

type SubagentTextBlockSegment = TextSegment & {
    readonly startedAtMs: number;
    readonly blockIndex: number;
    readonly streamOrder: number;
};

type SubagentStreamSegment = SubagentTextBlockSegment | InlineToolActivitySegment;

type SubagentToolResultModel = {
    statusRecord: JsonObject;
    resultText: string;
    streamSegments: MessageSegment[];
};

const requireResultRecord = (payload: JsonValue): JsonObject => {
    if (!isJsonObject(payload)) {
        throw new Error('Subagent tool result must be an object.');
    }
    return payload;
};

const requireSubagentRecord = (resultRecord: JsonObject): JsonObject => {
    const subagentValue = resultRecord['subagent'];
    if (!isJsonObject(subagentValue)) {
        throw new Error('Subagent tool result is missing subagent.');
    }
    return subagentValue;
};

const requireSubagentStreamRecord = (resultRecord: JsonObject): JsonObject => {
    const subagentStreamValue = resultRecord['subagentStream'];
    if (!isJsonObject(subagentStreamValue)) {
        throw new Error('Subagent tool result is missing subagent_stream.');
    }
    return subagentStreamValue;
};

const resolveSubagentTextStreamSegments = (streamRecord: JsonObject): SubagentTextBlockSegment[] => {
    const textBlocksValue = streamRecord['textBlocks'];
    if (!isJsonArray(textBlocksValue)) {
        throw new Error('Subagent tool result is missing subagent_stream.text_blocks.');
    }
    const result: SubagentTextBlockSegment[] = [];
    for (const entry of textBlocksValue) {
        if (!isJsonObject(entry)) {
            throw new Error('Subagent tool result contains an invalid text block.');
        }
        const text = entry['text'];
        const startedAtMs = readNonNegativeIntegerOrNullValue(entry['startedAtMs']);
        const blockIndex = readNonNegativeIntegerOrNullValue(entry['blockIndex']);
        const streamOrder = readNonNegativeIntegerOrNullValue(entry['streamOrder']);
        if (!isString(text) || startedAtMs === null || blockIndex === null || streamOrder === null) {
            throw new Error('Subagent tool result contains a text block with invalid fields.');
        }
        result.push({
            type: 'text',
            text,
            value: text,
            startedAtMs: startedAtMs,
            blockIndex: blockIndex,
            streamOrder: streamOrder
        });
    }
    return result;
};

const resolveSubagentSegmentStreamOrder = (segment: SubagentStreamSegment): number => {
    const streamOrder = segment.streamOrder;
    if (!isNumber(streamOrder) || !Number.isInteger(streamOrder) || streamOrder < 0) {
        throw new Error('Subagent stream segment ordering requires stream_order.');
    }
    return streamOrder;
};

const resolveSubagentSegmentStartedAtMs = (segment: SubagentStreamSegment): number => {
    const startedAtMs = segment.startedAtMs;
    if (!isNumber(startedAtMs) || !Number.isFinite(startedAtMs) || startedAtMs < 0) {
        throw new Error('Subagent stream segment ordering requires started_at_ms.');
    }
    return startedAtMs;
};

const compareSubagentTextBlock = (left: SubagentTextBlockSegment, right: SubagentTextBlockSegment): number => {
    if (left.blockIndex !== right.blockIndex) {
        return left.blockIndex - right.blockIndex;
    }
    return left.streamOrder - right.streamOrder;
};

const resolveSubagentVisibleText = (textSegments: SubagentTextBlockSegment[]): string => {
    const orderedTextSegments = [...textSegments].sort(compareSubagentTextBlock);
    const textParts: string[] = [];
    for (let index = 0; index < orderedTextSegments.length; index += 1) {
        const segment = orderedTextSegments[index];
        if (!segment || segment.blockIndex !== index) {
            throw new Error('Subagent stream text block indexes must be contiguous starting at 0.');
        }
        textParts.push(segment.value);
    }
    return textParts.join('');
};

const isTerminalSubagentStatusRecord = (statusRecord: JsonObject): boolean => {
    const statusValue = statusRecord['status'];
    if (!isString(statusValue)) {
        throw new Error('Subagent tool result status must be a string.');
    }
    const normalizedStatus = statusValue.trim();
    if (normalizedStatus === 'accepted' || normalizedStatus === 'running') {
        return false;
    }
    return true;
};

const mergeSubagentStreamSegments = (toolSegments: InlineToolActivitySegment[], textSegments: SubagentTextBlockSegment[], terminal: boolean): MessageSegment[] => {
    const merged: SubagentStreamSegment[] = [...toolSegments, ...textSegments];
    const seenStreamOrders = new Set<number>();
    for (const segment of merged) {
        const streamOrder = resolveSubagentSegmentStreamOrder(segment);
        resolveSubagentSegmentStartedAtMs(segment);
        if (seenStreamOrders.has(streamOrder)) {
            throw new Error('Subagent stream segment ordering requires unique stream_order values.');
        }
        seenStreamOrders.add(streamOrder);
    }
    const activities: AnchoredAssistantActivity[] = toolSegments.map((segment) => ({
        contentIndexBefore: segment.contentIndexBefore,
        eventSequence: resolveSubagentSegmentStreamOrder(segment),
        revisionSequence: resolveSubagentSegmentStreamOrder(segment),
        segment
    }));
    return resolveAnchoredAssistantSegments(
        {
            signatureSequence: null,
            text: resolveSubagentVisibleText(textSegments),
            active: false,
            terminal
        },
        activities,
        []
    );
};

const resolveSubagentToolResultModel = (payload: JsonValue, parentCallId: string, identity: { assistantTurnTimestamp: number; modelVariantIndex: number }): SubagentToolResultModel => {
    const resultRecord = requireResultRecord(payload);
    const subagentRecord = requireSubagentRecord(resultRecord);
    const resultTextValue = subagentRecord['resultText'];
    if (resultTextValue !== null && resultTextValue !== undefined && !isString(resultTextValue)) {
        throw new Error('Subagent tool result has invalid subagent.result_text.');
    }
    const streamRecord = requireSubagentStreamRecord(resultRecord);
    const rawToolCalls = streamRecord['toolCalls'];
    if (!isJsonArray(rawToolCalls)) {
        throw new Error('Subagent tool result is missing subagent_stream.tool_calls.');
    }
    const toolSegments: InlineToolActivitySegment[] = [];
    for (let index = 0; index < rawToolCalls.length; index += 1) {
        const rawToolCall = rawToolCalls[index];
        if (rawToolCall === undefined) {
            throw new Error('Subagent tool result contains an invalid child tool call.');
        }
        toolSegments.push(buildSubagentChildToolSegment(parentCallId, rawToolCall, identity));
    }
    const resultText = isString(resultTextValue) ? resultTextValue : '';
    const textSegments = resolveSubagentTextStreamSegments(streamRecord);
    return {
        statusRecord: subagentRecord,
        resultText,
        streamSegments: mergeSubagentStreamSegments(toolSegments, textSegments, isTerminalSubagentStatusRecord(subagentRecord))
    };
};

export type { SubagentToolResultModel };
export { resolveSubagentToolResultModel };
