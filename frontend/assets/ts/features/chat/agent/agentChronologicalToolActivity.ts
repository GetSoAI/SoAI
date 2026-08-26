/* SoAI - Chronological agent tool activity projection for assistant timelines [frontend/assets/ts/features/chat/agent/agentChronologicalToolActivity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCurrentLocale } from '@core/languageservice/service.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import type { ToolActivityCodeDiff } from '@features/chat/ChatTypes.ts';
import type { AgentIteration, AgentToolCallStatus } from '@core/chat/agentTypes.ts';
import { parseToolActivityQueryPayload } from '@features/chat/toolactivity/payloadTextParsing.ts';

interface TimelineToolActivityItem {
    callId: string;
    toolName: string;
    status: 'pending' | 'running' | 'completed' | 'cancelled' | 'error';
    inputArguments?: string;
    codeDiffs?: ToolActivityCodeDiff[];
    result?: JsonValue | null | undefined;
    error?: string;
    startedAtMs?: number;
    durationMs?: number;
    thinkingDurationBeforeMs?: number;
    sequenceIndex: number;
    contentIndexBefore: number;
    thinkingIndexBefore: number;
    collapsed: boolean;
}

interface ChronologicalToolActivityEntry {
    item: TimelineToolActivityItem;
    startedSequence: number;
    lastSequence: number;
    iterationIndex: number;
    contentIndexBefore: number;
    callId: string;
}

const resolveChronologyValue = (value: number, label: string): number => {
    if (!Number.isFinite(value) || value < 0) {
        throw new Error(`Agent chronology field "${label}" must be a non-negative finite number`);
    }
    return value;
};

const resolveToolStatus = (status: AgentToolCallStatus): TimelineToolActivityItem['status'] => {
    const statusMap: Record<AgentToolCallStatus, TimelineToolActivityItem['status']> = {
        pending: 'pending',
        running: 'running',
        completed: 'completed',
        cancelled: 'cancelled',
        error: 'error'
    };
    return statusMap[status];
};

const resolveFailureErrorText = (resultValue: JsonValue | null | undefined): string => {
    const parsed = typeof resultValue === 'string' ? parseToolActivityQueryPayload(resultValue) : resultValue;
    if (!isObject(parsed) || isArray(parsed)) {
        return typeof resultValue === 'string' ? resultValue : '';
    }
    const errorValue = parsed['error'];
    if (!isString(errorValue)) {
        return typeof resultValue === 'string' ? resultValue : '';
    }
    const normalized = errorValue.trim();
    return normalized ? normalized : typeof resultValue === 'string' ? resultValue : '';
};

const normalizeToolArguments = (argumentsValue: string | null): string | undefined => {
    if (typeof argumentsValue !== 'string') {
        return undefined;
    }
    const normalized = argumentsValue.trim();
    return normalized || undefined;
};

const normalizeCodeDiffEntries = (codeDiffs: ToolActivityCodeDiff[]): ToolActivityCodeDiff[] | undefined => {
    const normalizedDiffs: ToolActivityCodeDiff[] = [];
    for (const codeDiff of codeDiffs) {
        const diffValue = codeDiff.diff.replace(/\r\n/g, '\n').trim();
        if (!diffValue) {
            continue;
        }
        const pathValue = codeDiff.path.trim();
        const operationValue = codeDiff.operation.trim();
        normalizedDiffs.push({
            path: pathValue,
            operation: operationValue,
            diff: diffValue,
            truncated: codeDiff.truncated === true
        });
    }
    if (normalizedDiffs.length === 0) {
        return undefined;
    }
    return normalizedDiffs;
};

const buildChronologicalToolActivity = (orderedIterations: Array<[number, AgentIteration]>, iterationOffsets: Map<number, number>, collapsedByCallId: Map<string, boolean>): TimelineToolActivityItem[] => {
    const entriesByCallId = new Map<string, ChronologicalToolActivityEntry>();
    for (const [iterationIndex, iteration] of orderedIterations) {
        const iterationOffset = iterationOffsets.get(iterationIndex) ?? 0;
        for (const toolCall of iteration.toolCalls) {
            const callId = toolCall.toolCallId;
            const contentIndexBefore = Math.max(0, iterationOffset + Math.max(0, toolCall.textLengthBefore));
            const startedSequence = resolveChronologyValue(toolCall.startedSequence, 'started_sequence');
            const lastSequence = resolveChronologyValue(toolCall.lastSequence, 'last_sequence');
            const existingCollapsed = collapsedByCallId.get(callId);
            const nextItem: TimelineToolActivityItem = {
                callId: callId,
                toolName: toolCall.toolName,
                status: resolveToolStatus(toolCall.status),
                sequenceIndex: 0,
                contentIndexBefore: contentIndexBefore,
                thinkingIndexBefore: contentIndexBefore,
                collapsed: existingCollapsed === undefined ? true : existingCollapsed
            };
            const normalizedArguments = normalizeToolArguments(toolCall.inputArguments);
            if (normalizedArguments !== undefined) {
                nextItem.inputArguments = normalizedArguments;
            }
            if (toolCall.result !== null) {
                nextItem.result = toolCall.result;
            }
            if (toolCall.startedAtMs !== null) {
                nextItem.startedAtMs = toolCall.startedAtMs;
            }
            if (toolCall.durationMs !== null) {
                nextItem.durationMs = toolCall.durationMs;
            }
            const normalizedCodeDiffs = normalizeCodeDiffEntries(toolCall.codeDiffs);
            if (normalizedCodeDiffs !== undefined) {
                nextItem.codeDiffs = normalizedCodeDiffs;
            }
            if ((toolCall.status === 'cancelled' || toolCall.status === 'error') && toolCall.result !== null) {
                nextItem.error = resolveFailureErrorText(toolCall.result);
            }
            const existingEntry = entriesByCallId.get(callId);
            if (!existingEntry || lastSequence >= existingEntry.lastSequence) {
                entriesByCallId.set(callId, {
                    item: nextItem,
                    startedSequence: startedSequence,
                    lastSequence: lastSequence,
                    iterationIndex: iterationIndex,
                    contentIndexBefore: contentIndexBefore,
                    callId: callId
                });
            }
        }
    }
    const sortedEntries = Array.from(entriesByCallId.values()).sort((left, right) => {
        if (left.startedSequence !== right.startedSequence) {
            return left.startedSequence - right.startedSequence;
        }
        if (left.lastSequence !== right.lastSequence) {
            return left.lastSequence - right.lastSequence;
        }
        if (left.iterationIndex !== right.iterationIndex) {
            return left.iterationIndex - right.iterationIndex;
        }
        if (left.contentIndexBefore !== right.contentIndexBefore) {
            return left.contentIndexBefore - right.contentIndexBefore;
        }
        return left.callId.localeCompare(right.callId, getCurrentLocale());
    });
    return sortedEntries.map((entry, index) => ({
        ...entry.item,
        sequenceIndex: index
    }));
};

export { buildChronologicalToolActivity };
export type { TimelineToolActivityItem };
