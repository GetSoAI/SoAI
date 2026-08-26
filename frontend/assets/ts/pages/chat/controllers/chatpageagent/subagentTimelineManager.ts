/* SoAI - Chat page subagent timeline manager [frontend/assets/ts/pages/chat/controllers/chatpageagent/subagentTimelineManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { AgentSubagentState, AgentSubagentStatus } from '@core/chat/agentSubagentTypes.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { isArray, isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { buildParentToolCallResultPayload, buildSubagentParentToolCallId, resolveSubagentIdFromParentToolCallId, type TimelineToolActivityItem } from '@features/chat/public.ts';

const resolveSubagentTimelineStatus = (status: AgentSubagentStatus): TimelineToolActivityItem['status'] => {
    if (status === 'accepted') {
        return 'pending';
    }
    if (status === 'running') {
        return 'running';
    }
    if (status === 'completed') {
        return 'completed';
    }
    if (status === 'max_iterations') {
        return 'completed';
    }
    if (status === 'cancelled') {
        return 'cancelled';
    }
    return 'error';
};

const buildSubagentArguments = (subagent: AgentSubagentState): Record<string, JsonValue> => {
    return {
        query: subagent.displayName ?? subagent.subagentId,
        subagentId: subagent.subagentId,
        mode: subagent.mode,
        status: subagent.status,
        parentIterationIndex: subagent.parentIterationIndex,
        requestedModel: subagent.requestedModel
    };
};

const parseSubagentPromptFromArguments = (argumentsText: string): { task: string | null; context: string | null } | null => {
    const trimmed = toTrimmedString(argumentsText);
    if (!trimmed) {
        return null;
    }
    let parsed: JsonValue;
    try {
        parsed = parseRequiredJsonText(trimmed);
    } catch (error) {
        errorHandler.warn('ChatPageAgentSubagentTimeline', 'Failed to parse subagent_spawn arguments while extracting prompt', ensureError(error));
        return null;
    }
    if (!isObject(parsed) || isArray(parsed)) {
        return null;
    }
    const taskValue = parsed['task'];
    const contextValue = parsed['context'];
    const task = toTrimmedString(taskValue);
    const context = toTrimmedString(contextValue);
    if (!task && !context) {
        return null;
    }
    return {
        task: task ? task : null,
        context: context ? context : null
    };
};

const buildSubagentPromptByParentToolCallId = (toolActivity: TimelineToolActivityItem[]): Map<string, { task: string | null; context: string | null }> => {
    const promptByParentCallId = new Map<string, { task: string | null; context: string | null }>();
    for (const item of toolActivity) {
        if (item.toolName.trim() !== 'subagent_spawn') {
            continue;
        }
        const rawArguments = typeof item.inputArguments === 'string' ? item.inputArguments : '';
        const prompt = parseSubagentPromptFromArguments(rawArguments);
        if (!prompt) {
            continue;
        }
        promptByParentCallId.set(item.callId, prompt);
    }
    return promptByParentCallId;
};

const buildSubagentArgumentsWithPrompt = (subagent: AgentSubagentState, promptByParentToolCallId: Map<string, { task: string | null; context: string | null }>): Record<string, JsonValue> => {
    const inputArguments = buildSubagentArguments(subagent);
    const prompt = promptByParentToolCallId.get(subagent.parentToolCallId) ?? null;
    if (!prompt) {
        return inputArguments;
    }
    if (prompt.task) {
        inputArguments['task'] = prompt.task;
    }
    if (prompt.context) {
        inputArguments['context'] = prompt.context;
    }
    return inputArguments;
};

const buildSubagentResult = (subagent: AgentSubagentState, convId: string): Record<string, JsonValue> => {
    return buildParentToolCallResultPayload(subagent, convId);
};

const buildSubagentActivityItems = (toolActivity: TimelineToolActivityItem[], subagents: Map<string, AgentSubagentState>, collapsedByCallId: Map<string, boolean>, iterationOffsets: Map<number, number>, combinedTextLength: number, convId: string): TimelineToolActivityItem[] => {
    const promptByParentToolCallId = buildSubagentPromptByParentToolCallId(toolActivity);
    const items: TimelineToolActivityItem[] = [];
    for (const subagent of subagents.values()) {
        const callId = buildSubagentParentToolCallId(subagent.subagentId);
        const contentIndexBefore = iterationOffsets.get(subagent.parentIterationIndex) ?? combinedTextLength;
        const collapsed = collapsedByCallId.get(callId);
        const item: TimelineToolActivityItem = {
            callId: callId,
            toolName: 'subagent_spawn',
            status: resolveSubagentTimelineStatus(subagent.status),
            sequenceIndex: 0,
            contentIndexBefore: contentIndexBefore,
            thinkingIndexBefore: contentIndexBefore,
            collapsed: collapsed === undefined ? true : collapsed,
            inputArguments: JSON.stringify(buildSubagentArgumentsWithPrompt(subagent, promptByParentToolCallId)),
            startedAtMs: subagent.startedAtMs
        };
        item.result = buildSubagentResult(subagent, convId);
        if (subagent.finishedAtMs !== null) {
            item.durationMs = Math.max(0, subagent.finishedAtMs - subagent.startedAtMs);
        }
        if (subagent.status === 'error' || subagent.status === 'cancelled' || subagent.status === 'abandoned') {
            item.error = subagent.errorMessage ?? subagent.status;
        }
        items.push(item);
    }
    return items;
};

const compareSubagentItems = (left: TimelineToolActivityItem, right: TimelineToolActivityItem, subagents: Map<string, AgentSubagentState>): number => {
    const leftSubagentId = resolveSubagentIdFromParentToolCallId(left.callId);
    const rightSubagentId = resolveSubagentIdFromParentToolCallId(right.callId);
    const leftSubagent = leftSubagentId === null ? null : subagents.get(leftSubagentId);
    const rightSubagent = rightSubagentId === null ? null : subagents.get(rightSubagentId);
    if (!leftSubagent || !rightSubagent) {
        return left.callId.localeCompare(right.callId, getCurrentLocale());
    }
    if (leftSubagent.startedAtMs !== rightSubagent.startedAtMs) {
        return leftSubagent.startedAtMs - rightSubagent.startedAtMs;
    }
    if (leftSubagent.displayOrder !== rightSubagent.displayOrder) {
        return leftSubagent.displayOrder - rightSubagent.displayOrder;
    }
    return left.callId.localeCompare(right.callId, getCurrentLocale());
};

const mergeSubagentActivity = (toolActivity: TimelineToolActivityItem[], subagents: Map<string, AgentSubagentState>, collapsedByCallId: Map<string, boolean>, iterationOffsets: Map<number, number>, combinedTextLength: number, convId: string): TimelineToolActivityItem[] => {
    if (subagents.size === 0) {
        return toolActivity;
    }
    const subagentItems = buildSubagentActivityItems(toolActivity, subagents, collapsedByCallId, iterationOffsets, combinedTextLength, convId);
    const itemsByParentCallId = new Map<string, TimelineToolActivityItem[]>();
    const unmatchedItems: TimelineToolActivityItem[] = [];
    for (const item of subagentItems) {
        const subagentId = resolveSubagentIdFromParentToolCallId(item.callId);
        const subagent = subagentId === null ? null : subagents.get(subagentId);
        if (!subagent || !subagent.parentToolCallId.trim()) {
            unmatchedItems.push(item);
            continue;
        }
        const relatedItems = itemsByParentCallId.get(subagent.parentToolCallId) ?? [];
        relatedItems.push(item);
        itemsByParentCallId.set(subagent.parentToolCallId, relatedItems);
    }
    const merged: TimelineToolActivityItem[] = [];
    for (const item of toolActivity) {
        merged.push(item);
        const relatedItems = itemsByParentCallId.get(item.callId);
        if (!relatedItems) {
            continue;
        }
        relatedItems.sort((left, right) => compareSubagentItems(left, right, subagents));
        for (const relatedItem of relatedItems) {
            merged.push(relatedItem);
        }
        itemsByParentCallId.delete(item.callId);
    }
    for (const relatedItems of itemsByParentCallId.values()) {
        for (const relatedItem of relatedItems) {
            unmatchedItems.push(relatedItem);
        }
    }
    unmatchedItems.sort((left, right) => compareSubagentItems(left, right, subagents));
    return merged.concat(unmatchedItems).map((item, index) => ({
        ...item,
        sequenceIndex: index
    }));
};

export { mergeSubagentActivity };
