/* SoAI - Chat running activity summary counting [frontend/assets/ts/features/chat/toolactivity/runningActivitySummaryCounting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { readNonNegativeIntegerOrNullValue } from '@core/types/payloadNumberReaders.ts';
import { isJsonArray, isJsonObject, isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import { tryResolveAcceptedSubagentPayloadRecord } from '@features/chat/agent/agentSubagentToolResult.ts';
import { isShellSessionInProgressToolResult } from '@features/chat/agent/agentShellSessionResultParsing.ts';
import type { ChatMessage, ToolActivityItem, ToolActivityStatus } from '@features/chat/ChatTypes.ts';
import { buildSubagentChildToolCallId } from '@features/chat/message/messageview/subagentToolCallSegments.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';
import { isToolActivityStatus } from '@features/chat/toolactivity/toolActivityStatus.ts';

type RunningActivityTarget = {
    ancestorCallIds: string[];
    callId: string;
    startedAtMs: number;
};

type RunningActivityCounts = {
    activityCount: number;
    nextVisibleAtMs: number | null;
    subagentCount: number;
    target: RunningActivityTarget | null;
};

type NestedToolCall = {
    callId: string;
    toolName: string;
    status: ToolActivityStatus;
    result: JsonValue | undefined;
    startedAtMs: number | null;
};

type DurableBackgroundToolActivity = Pick<NestedToolCall, 'toolName' | 'status'> & { result?: JsonValue | undefined };

const RUNNING_ACTIVITY_COUNT_DELAY_MS = 10000;

const isActiveStatus = (status: ToolActivityStatus): boolean => status === 'pending' || status === 'running';

const isCompletedStatus = (status: ToolActivityStatus): boolean => status === 'completed';

const isSubagentStatusValueActive = (value: JsonValue | null | undefined): boolean => value === 'accepted' || value === 'running' || value === 'pending';

const parseNestedToolCall = (value: JsonValue): NestedToolCall | null => {
    if (!isJsonObject(value)) {
        return null;
    }
    const toolName = value['toolName'];
    const status = value['status'];
    if (!isString(toolName) || !toolName.trim()) {
        return null;
    }
    if (!isToolActivityStatus(status)) {
        return null;
    }
    const callId = value['callId'];
    if (!isString(callId) || !callId.trim()) {
        return null;
    }
    const startedAtMs = readNonNegativeIntegerOrNullValue(value['startedAtMs']);
    const result = value['result'];
    if (result !== undefined && !isJsonValue(result)) {
        return null;
    }
    return {
        callId: callId.trim(),
        toolName: toolName.trim(),
        status,
        result,
        startedAtMs
    };
};

const resolveNestedToolCalls = (result: JsonValue | undefined): JsonValue[] => {
    const parsedSubagent = tryResolveAcceptedSubagentPayloadRecord(result);
    if (parsedSubagent === null) {
        return [];
    }
    if (!isJsonObject(result)) {
        return [];
    }
    const streamValue = result['subagentStream'];
    if (!isJsonObject(streamValue)) {
        return [];
    }
    const toolCalls = streamValue['toolCalls'];
    if (!isJsonArray(toolCalls)) {
        return [];
    }
    return [...toolCalls];
};

const isShellActivityRunning = (status: ToolActivityStatus, result: JsonValue | undefined): boolean => {
    if (isActiveStatus(status)) {
        return true;
    }
    return isCompletedStatus(status) && isShellSessionInProgressToolResult(result);
};

const isCountedActivityRunning = (toolName: string, status: ToolActivityStatus, result: JsonValue | undefined): boolean => {
    const leafName = normalizeToolLeafName(toolName);
    if (leafName === 'shell') {
        return isShellActivityRunning(status, result);
    }
    if (leafName === 'hardware_benchmark') {
        return isActiveStatus(status);
    }
    return false;
};

const isSubagentSpawnRunning = (tool: DurableBackgroundToolActivity): boolean => {
    if (isActiveStatus(tool.status)) {
        return true;
    }
    if (!isCompletedStatus(tool.status)) {
        return false;
    }
    const subagent = tryResolveAcceptedSubagentPayloadRecord(tool.result);
    return subagent !== null && isSubagentStatusValueActive(subagent['status']);
};

const isDurableBackgroundToolActivity = (tool: DurableBackgroundToolActivity): boolean => {
    return isCountedActivityRunning(tool.toolName, tool.status, tool.result) || (normalizeToolLeafName(tool.toolName) === 'subagent_spawn' && isSubagentSpawnRunning(tool));
};

const hasRunningBackgroundWork = (tool: DurableBackgroundToolActivity): boolean => {
    if (isDurableBackgroundToolActivity(tool)) {
        return true;
    }
    if (normalizeToolLeafName(tool.toolName) !== 'subagent_spawn') {
        return false;
    }
    return resolveNestedToolCalls(tool.result).some((rawToolCall) => {
        const toolCall = parseNestedToolCall(rawToolCall);
        return toolCall !== null && hasRunningBackgroundWork(toolCall);
    });
};

const newerRunningActivityTarget = (current: RunningActivityTarget | null, candidate: RunningActivityTarget): RunningActivityTarget => {
    if (current === null || candidate.startedAtMs >= current.startedAtMs) {
        return candidate;
    }
    return current;
};

const earlierVisibleAtMs = (current: number | null, candidate: number): number => {
    if (current === null || candidate < current) {
        return candidate;
    }
    return current;
};

const applyRunningTargetCount = (counts: RunningActivityCounts, target: RunningActivityTarget | null, nowMs: number, counterType: 'activity' | 'subagent'): void => {
    if (target === null) {
        return;
    }
    if (nowMs - target.startedAtMs < RUNNING_ACTIVITY_COUNT_DELAY_MS) {
        counts.nextVisibleAtMs = earlierVisibleAtMs(counts.nextVisibleAtMs, target.startedAtMs + RUNNING_ACTIVITY_COUNT_DELAY_MS);
        return;
    }
    if (counterType === 'activity') {
        counts.activityCount += 1;
    } else {
        counts.subagentCount += 1;
    }
    counts.target = newerRunningActivityTarget(counts.target, target);
};

const mergeRunningActivityCounts = (counts: RunningActivityCounts, incoming: RunningActivityCounts): void => {
    counts.activityCount += incoming.activityCount;
    counts.subagentCount += incoming.subagentCount;
    if (incoming.target !== null) {
        counts.target = newerRunningActivityTarget(counts.target, incoming.target);
    }
    if (incoming.nextVisibleAtMs !== null) {
        counts.nextVisibleAtMs = earlierVisibleAtMs(counts.nextVisibleAtMs, incoming.nextVisibleAtMs);
    }
};

const targetFromTool = (tool: ToolActivityItem): RunningActivityTarget | null => {
    const startedAtMs = readNonNegativeIntegerOrNullValue(tool.startedAtMs);
    if (startedAtMs === null) {
        return null;
    }
    return {
        ancestorCallIds: [],
        callId: tool.callId,
        startedAtMs
    };
};

const targetFromNestedTool = (parentCallId: string, ancestorCallIds: string[], tool: NestedToolCall): RunningActivityTarget | null => {
    if (tool.startedAtMs === null) {
        return null;
    }
    return {
        ancestorCallIds: [parentCallId, ...ancestorCallIds],
        callId: buildSubagentChildToolCallId(parentCallId, tool.callId),
        startedAtMs: tool.startedAtMs
    };
};

const countNestedRunningWork = (result: JsonValue | undefined, parentCallId: string, ancestorCallIds: string[], nowMs: number): RunningActivityCounts => {
    const counts = createRunningActivityCounts();
    for (const rawToolCall of resolveNestedToolCalls(result)) {
        const toolCall = parseNestedToolCall(rawToolCall);
        if (toolCall === null) {
            continue;
        }
        if (isCountedActivityRunning(toolCall.toolName, toolCall.status, toolCall.result)) {
            applyRunningTargetCount(counts, targetFromNestedTool(parentCallId, ancestorCallIds, toolCall), nowMs, 'activity');
        }
        if (normalizeToolLeafName(toolCall.toolName) === 'subagent_spawn') {
            const subagentTarget = targetFromNestedTool(parentCallId, ancestorCallIds, toolCall);
            if (isSubagentSpawnRunning(toolCall)) {
                applyRunningTargetCount(counts, subagentTarget, nowMs, 'subagent');
            }
            const nestedParentCallId = subagentTarget === null ? buildSubagentChildToolCallId(parentCallId, toolCall.callId) : subagentTarget.callId;
            const nestedAncestorCallIds = subagentTarget === null ? [parentCallId, ...ancestorCallIds] : subagentTarget.ancestorCallIds;
            mergeRunningActivityCounts(counts, countNestedRunningWork(toolCall.result, nestedParentCallId, nestedAncestorCallIds, nowMs));
        }
    }
    return counts;
};

const createRunningActivityCounts = (): RunningActivityCounts => ({
    activityCount: 0,
    nextVisibleAtMs: null,
    subagentCount: 0,
    target: null
});

const applyToolActivityToRunningCounts = (counts: RunningActivityCounts, tool: ToolActivityItem, nowMs: number): void => {
    if (isCountedActivityRunning(tool.toolName, tool.status, tool.result)) {
        applyRunningTargetCount(counts, targetFromTool(tool), nowMs, 'activity');
    }
    if (normalizeToolLeafName(tool.toolName) !== 'subagent_spawn') {
        return;
    }
    const subagentTarget = targetFromTool(tool);
    if (isSubagentSpawnRunning(tool)) {
        applyRunningTargetCount(counts, subagentTarget, nowMs, 'subagent');
    }
    mergeRunningActivityCounts(counts, countNestedRunningWork(tool.result, tool.callId, [], nowMs));
};

const resolveResultActivityState = (toolName: string, status: ToolActivityStatus, result: JsonValue | undefined): string => {
    const leafName = normalizeToolLeafName(toolName);
    if (leafName === 'shell') {
        return isShellActivityRunning(status, result) ? 'shell-open' : 'shell-closed';
    }
    if (leafName !== 'subagent_spawn') {
        return '';
    }
    const subagent = tryResolveAcceptedSubagentPayloadRecord(result);
    const subagentStatus = subagent === null ? '' : String(subagent['status'] ?? '');
    return [`subagent:${status}:${subagentStatus}`, ...resolveNestedToolCalls(result).map(resolveNestedToolCallFingerprint)].join(',');
};

const resolveNestedToolCallFingerprint = (value: JsonValue): string => {
    const tool = parseNestedToolCall(value);
    if (tool === null) {
        return 'invalid';
    }
    return [tool.callId, tool.toolName, tool.status, String(tool.startedAtMs ?? ''), resolveResultActivityState(tool.toolName, tool.status, tool.result)].join(':');
};

const resolveCountedRunningActivitySummaryFingerprint = (message: ChatMessage): string | null => {
    const projections = message.toolCallProjections;
    if (!Array.isArray(projections) || projections.length === 0) {
        return null;
    }
    const timeline = message.assistantEventTimeline;
    const timelineLength = Array.isArray(timeline) ? timeline.length : 0;
    const projectionFingerprint = projections
        .map((tool) => {
            if (!isString(tool.callId) || !isString(tool.toolName) || !isToolActivityStatus(tool.status)) {
                return 'invalid';
            }
            return [tool.callId, tool.toolName, tool.status, String(tool.startedAtMs ?? ''), String(tool.sequenceIndex ?? ''), resolveResultActivityState(tool.toolName, tool.status, tool.result)].join(':');
        })
        .join('|');
    return `${String(timelineLength)}|${projectionFingerprint}`;
};

export { applyToolActivityToRunningCounts, createRunningActivityCounts, hasRunningBackgroundWork, isDurableBackgroundToolActivity, resolveCountedRunningActivitySummaryFingerprint };
export type { DurableBackgroundToolActivity, RunningActivityCounts, RunningActivityTarget };
