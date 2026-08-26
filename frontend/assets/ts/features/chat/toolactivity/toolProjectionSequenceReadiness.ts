/* SoAI - Tool projection sequence readiness [frontend/assets/ts/features/chat/toolactivity/toolProjectionSequenceReadiness.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray } from '@core/typeGuards.ts';
import type { ChatMessage, ToolActivityItem } from '@features/chat/ChatTypes.ts';
import { mapDecodedAssistantTimelineTool } from '@features/chat/assistanteventtimeline/toolPayloadMapper.ts';
import { canAttachSequenceIndexOwner } from '@features/chat/assistanteventtimeline/timelineSequenceIndexValidation.ts';

const TOOL_TIMELINE_EVENT_TYPES = new Set(['tool_call_created', 'tool_call_started', 'tool_call_completed']);

const registerToolSequenceOwner = (sequenceOwnerByIndex: Map<number, string>, tool: ToolActivityItem): boolean => {
    if (!canAttachSequenceIndexOwner(sequenceOwnerByIndex, tool.sequenceIndex, tool.callId)) {
        return false;
    }
    if (!sequenceOwnerByIndex.has(tool.sequenceIndex)) {
        sequenceOwnerByIndex.set(tool.sequenceIndex, tool.callId);
    }
    return true;
};

const registerTimelineToolOwners = (message: ChatMessage, sequenceOwnerByIndex: Map<number, string>): boolean => {
    const timeline = message.assistantEventTimeline;
    if (!isArray(timeline)) {
        return true;
    }
    for (const event of timeline) {
        if (!TOOL_TIMELINE_EVENT_TYPES.has(event.eventType)) {
            continue;
        }
        const payloadTool = event.payload.tool;
        const tool = payloadTool === undefined ? null : mapDecodedAssistantTimelineTool(payloadTool);
        if (tool === null || !registerToolSequenceOwner(sequenceOwnerByIndex, tool)) {
            return false;
        }
    }
    return true;
};

const registerProjectionOwners = (message: ChatMessage, projection: ToolActivityItem, sequenceOwnerByIndex: Map<number, string>): boolean => {
    const projections = message.toolCallProjections;
    if (!isArray(projections)) {
        return registerToolSequenceOwner(sequenceOwnerByIndex, projection);
    }
    const projectionsBySequence = [...projections, projection].sort((left, right) => left.sequenceIndex - right.sequenceIndex);
    for (const projection of projectionsBySequence) {
        if (!registerToolSequenceOwner(sequenceOwnerByIndex, projection)) {
            return false;
        }
    }
    return true;
};

const canApplyToolCallProjectionWithoutSequenceGap = (message: ChatMessage, projection: ToolActivityItem): boolean => {
    const sequenceOwnerByIndex = new Map<number, string>();
    if (!registerTimelineToolOwners(message, sequenceOwnerByIndex)) {
        return false;
    }
    if (!registerProjectionOwners(message, projection, sequenceOwnerByIndex)) {
        return false;
    }
    return true;
};

export { canApplyToolCallProjectionWithoutSequenceGap };
