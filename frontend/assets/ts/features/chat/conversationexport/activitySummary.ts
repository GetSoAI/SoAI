/* SoAI - Conversation export activity summary resolution [frontend/assets/ts/features/chat/conversationexport/activitySummary.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isNonEmptyString, isPlainObject } from '@core/typeGuards.ts';
import type { ChatMessage, ToolActivityItem, ToolCall } from '@features/chat/ChatTypes.ts';
import { mapDecodedAssistantTimelineTool } from '@features/chat/assistanteventtimeline/toolPayloadMapper.ts';
import type { MessageSegment, ToolCallSegment } from '@features/chat/message/messageSegments.ts';
import { normalizeToolName } from '@features/chat/message/toolActivityPayloadFormatting.ts';
import { resolveToolActivityStatusLabel } from '@features/chat/message/toolActivityStatusLabel.ts';

type ConversationExportActivitySummary = {
    toolCalls: number;
    labels: string[];
};

const isToolCallSegment = (segment: MessageSegment): segment is ToolCallSegment => segment.type === 'tool_call';

const resolveToolCallName = (toolCall: ToolCall): string => {
    const toolFunction = toolCall.function;
    if (toolFunction !== null && toolFunction !== undefined) {
        const functionName = toolFunction.name;
        if (isNonEmptyString(functionName)) {
            return functionName.trim();
        }
    }
    return '';
};

const resolveToolCallSegmentName = (segment: ToolCallSegment): string => {
    if (isNonEmptyString(segment.name)) {
        return segment.name.trim();
    }
    const functionValue = segment.function;
    if (isPlainObject(functionValue)) {
        const functionName = functionValue['name'];
        if (isNonEmptyString(functionName)) {
            return functionName.trim();
        }
    }
    return '';
};

const formatActivityLabel = (toolName: string, status: ToolActivityItem['status'] | null): string => {
    const normalizedName = normalizeToolName(toolName);
    const statusLabel = status === null ? '' : resolveToolActivityStatusLabel(status).trim();
    return statusLabel ? `${normalizedName} (${statusLabel})` : normalizedName;
};

const appendNamedActivityLabel = (labels: string[], toolName: string, status: ToolActivityItem['status'] | null): void => {
    const trimmedName = toolName.trim();
    if (trimmedName) {
        labels.push(formatActivityLabel(trimmedName, status));
    }
};

const collectTimelineActivities = (message: ChatMessage, activitiesByCallId: Map<string, ToolActivityItem>): void => {
    const timeline = message.assistantEventTimeline;
    if (!isArray(timeline)) {
        return;
    }
    for (const event of timeline) {
        const toolPayload = event.payload.tool;
        if (toolPayload !== undefined) {
            const activity = mapDecodedAssistantTimelineTool(toolPayload);
            activitiesByCallId.set(activity.callId, activity);
        }
    }
};

const collectProjectedActivities = (message: ChatMessage, activitiesByCallId: Map<string, ToolActivityItem>): void => {
    const projections = message.toolCallProjections;
    if (!isArray(projections)) {
        return;
    }
    for (const projection of projections) {
        activitiesByCallId.set(projection.callId, projection);
    }
};

const collectActivities = (message: ChatMessage): ToolActivityItem[] => {
    const activitiesByCallId = new Map<string, ToolActivityItem>();
    collectTimelineActivities(message, activitiesByCallId);
    collectProjectedActivities(message, activitiesByCallId);
    return Array.from(activitiesByCallId.values());
};

const collectDeclaredToolCallLabels = (message: ChatMessage): string[] => {
    const labels: string[] = [];
    if (isArray(message.toolCalls)) {
        for (const toolCall of message.toolCalls) {
            appendNamedActivityLabel(labels, resolveToolCallName(toolCall), null);
        }
    }
    return labels;
};

const collectSegmentToolCallLabels = (segments: readonly MessageSegment[]): string[] => {
    const labels: string[] = [];
    for (const segment of segments) {
        if (isToolCallSegment(segment)) {
            appendNamedActivityLabel(labels, resolveToolCallSegmentName(segment), null);
        }
    }
    return labels;
};

const collectFallbackActivityLabels = (message: ChatMessage, segments: readonly MessageSegment[]): string[] => {
    const declaredLabels = collectDeclaredToolCallLabels(message);
    const segmentLabels = collectSegmentToolCallLabels(segments);
    return declaredLabels.length >= segmentLabels.length ? declaredLabels : segmentLabels;
};

const resolveConversationExportActivitySummary = (message: ChatMessage, segments: readonly MessageSegment[]): ConversationExportActivitySummary => {
    const activities = collectActivities(message);
    const activityLabels = activities.map((activity) => formatActivityLabel(activity.toolName, activity.status));
    const fallbackLabels = collectFallbackActivityLabels(message, segments);
    const toolCalls = Math.max(activities.length, fallbackLabels.length);
    return {
        toolCalls,
        labels: activityLabels.length > 0 ? activityLabels : fallbackLabels
    };
};

export { resolveConversationExportActivitySummary };
