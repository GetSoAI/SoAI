/* SoAI - Assistant event timeline projection for agent turns [frontend/assets/ts/features/chat/agent/agentAssistantTimelineProjection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { isNonNegativeInteger } from '@core/typeGuards.ts';
import type { AssistantEventTimelineItem } from '@features/chat/ChatTypes.ts';
import type { TimelineToolActivityItem } from '@features/chat/agent/agentChronologicalToolActivity.ts';
import { countAgentTextCodePoints, createAgentTextForwardCursor } from '@features/chat/agent/agentTextMetrics.ts';
import type { AgentIteration } from '@core/chat/agentTypes.ts';

type CombinedIterationText = {
    combinedText: string;
    combinedTextCodePointCount: number;
    iterationOffsets: Map<number, number>;
};

const buildToolPayload = (item: TimelineToolActivityItem, contentIndexBefore: number): JsonObject => {
    if (!isNonNegativeInteger(item.thinkingIndexBefore)) {
        throw new Error('Agent tool activity thinking_index_before must match thinking chronology.');
    }
    const toolPayload: JsonObject = {
        callId: item.callId,
        toolName: item.toolName,
        status: item.status,
        sequenceIndex: item.sequenceIndex,
        contentIndexBefore: contentIndexBefore,
        thinkingIndexBefore: item.thinkingIndexBefore,
        collapsed: item.collapsed
    };
    if (item.inputArguments !== undefined) {
        toolPayload['arguments'] = item.inputArguments;
    }
    if (item.result !== undefined) {
        toolPayload['result'] = item.result;
    }
    if (item.error !== undefined) {
        toolPayload['error'] = item.error;
    }
    if (item.durationMs !== undefined) {
        toolPayload['duration_ms'] = item.durationMs;
    }
    if (item.startedAtMs !== undefined) {
        toolPayload['started_at_ms'] = item.startedAtMs;
    }
    if (item.thinkingDurationBeforeMs !== undefined) {
        toolPayload['thinking_duration_before_ms'] = item.thinkingDurationBeforeMs;
    }
    if (item.codeDiffs !== undefined) {
        toolPayload['code_diffs'] = item.codeDiffs.map((codeDiff) => ({
            path: codeDiff.path,
            operation: codeDiff.operation,
            diff: codeDiff.diff,
            truncated: codeDiff.truncated
        }));
    }
    return toolPayload;
};

const resolveToolContentAnchor = (item: TimelineToolActivityItem, contentLength: number): number => {
    const indexBefore = item.contentIndexBefore;
    if (!isNonNegativeInteger(indexBefore) || indexBefore > contentLength) {
        throw new Error('Agent tool activity content_index_before must match assistant text chronology.');
    }
    return indexBefore;
};

const requireMonotonicContentAnchor = (indexBefore: number, cursor: number): void => {
    if (indexBefore < cursor) {
        throw new Error('Agent tool activity content_index_before must be monotonic.');
    }
};

const buildAgentAssistantEventTimeline = (assistantTimestamp: number, content: string, toolActivity: TimelineToolActivityItem[]): AssistantEventTimelineItem[] => {
    const timeline: AssistantEventTimelineItem[] = [];
    const pushEvent = (eventType: string, payload: JsonObject): void => {
        const sequence = timeline.length;
        const assistantRevision = sequence + 1;
        timeline.push({
            sequence,
            assistantRevision: assistantRevision,
            eventType: eventType,
            payload: {
                assistantAtMs: assistantTimestamp,
                assistantRevision: assistantRevision,
                ...payload
            }
        });
    };

    const pushAssistantTextDelta = (delta: string): void => {
        if (delta.length === 0) {
            return;
        }
        pushEvent('assistant_text_delta', { delta });
    };

    const pushToolEvent = (item: TimelineToolActivityItem, contentIndexBefore: number): void => {
        const toolEventType = item.status === 'pending' ? 'tool_call_created' : item.status === 'running' ? 'tool_call_started' : 'tool_call_completed';
        pushEvent(toolEventType, { tool: buildToolPayload(item, contentIndexBefore) });
    };

    let cursor = 0;
    let cursorUnitIndex = 0;
    const contentLength = countAgentTextCodePoints(content);
    const contentCursor = createAgentTextForwardCursor(content);
    for (const item of toolActivity) {
        const indexBefore = resolveToolContentAnchor(item, contentLength);
        requireMonotonicContentAnchor(indexBefore, cursor);
        if (indexBefore > cursor) {
            const indexBeforeUnitIndex = contentCursor.unitIndexAtCodePointIndex(indexBefore);
            pushAssistantTextDelta(content.slice(cursorUnitIndex, indexBeforeUnitIndex));
            cursor = indexBefore;
            cursorUnitIndex = indexBeforeUnitIndex;
        }
        pushToolEvent(item, indexBefore);
    }
    if (cursor < contentLength) {
        pushAssistantTextDelta(content.slice(cursorUnitIndex));
    }
    return timeline;
};

const combineIterationText = (orderedIterations: Array<[number, AgentIteration]>): CombinedIterationText => {
    const segments: string[] = [];
    let boundaryUnitIndex = 0;
    const boundaryUnitIndexByIteration = new Map<number, number>();
    for (const [iterationIndex, iteration] of orderedIterations) {
        boundaryUnitIndexByIteration.set(iterationIndex, boundaryUnitIndex);
        segments.push(iteration.text);
        boundaryUnitIndex += iteration.text.length;
    }
    const combinedText = segments.join('');
    const combinedTextCursor = createAgentTextForwardCursor(combinedText);
    const iterationOffsets = new Map<number, number>();
    for (const [iterationIndex, unitIndex] of boundaryUnitIndexByIteration) {
        iterationOffsets.set(iterationIndex, combinedTextCursor.codePointIndexAtUnitIndex(unitIndex));
    }
    return { combinedText, combinedTextCodePointCount: combinedTextCursor.codePointIndexAtUnitIndex(combinedText.length), iterationOffsets };
};

const hasChatStreamLoadingActivityTimeline = (timeline: AssistantEventTimelineItem[] | undefined): boolean => {
    if (!timeline) {
        return false;
    }
    for (const entry of timeline) {
        const eventType = entry.eventType;
        if (eventType === 'loading_activity') {
            return true;
        }
    }
    return false;
};

export { buildAgentAssistantEventTimeline, combineIterationText, hasChatStreamLoadingActivityTimeline };
export type { CombinedIterationText };
