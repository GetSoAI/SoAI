/* SoAI - Tool activity detail hydration policy [frontend/assets/ts/features/chat/toolactivity/toolDetailsHydrationPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage, ToolActivityItem } from '@features/chat/ChatTypes.ts';
import { mapDecodedAssistantTimelineTool } from '@features/chat/assistanteventtimeline/toolPayloadMapper.ts';
import { toolRunningResultIsDetailHydrated } from '@features/chat/toolactivity/toolLiveResultPolicy.ts';
import { toolProjectionHasHydratedInlineMedia, toolProjectionNeedsMediaHydration } from '@features/chat/toolactivity/toolResultMediaHydration.ts';

const toolProjectionNeedsDetailHydration = (projection: ToolActivityItem | null): boolean => {
    return projection !== null && (toolProjectionNeedsMediaHydration(projection) || toolRunningResultIsDetailHydrated(projection.toolName));
};

const toolProjectionProvidesHydratedDetails = (projection: ToolActivityItem | null): boolean => {
    return projection !== null && (toolProjectionHasHydratedInlineMedia(projection) || toolRunningResultIsDetailHydrated(projection.toolName));
};

const messageContainsToolHydrationCandidate = (message: ChatMessage, callId: string, predicate: (projection: ToolActivityItem | null) => boolean): boolean => {
    if (Array.isArray(message.toolCallProjections)) {
        for (const projection of message.toolCallProjections) {
            if (projection.callId === callId && predicate(projection)) {
                return true;
            }
        }
    }
    if (!Array.isArray(message.assistantEventTimeline)) {
        return false;
    }
    for (const item of message.assistantEventTimeline) {
        const toolPayload = item.payload.tool;
        const projection = toolPayload === undefined ? null : mapDecodedAssistantTimelineTool(toolPayload);
        if (projection !== null && projection.callId === callId && predicate(projection)) {
            return true;
        }
    }
    return false;
};

const messageContainsToolMediaHydrationCandidate = (message: ChatMessage, callId: string): boolean => messageContainsToolHydrationCandidate(message, callId, toolProjectionNeedsMediaHydration);

const messageContainsToolDetailHydrationCandidate = (message: ChatMessage, callId: string): boolean => messageContainsToolHydrationCandidate(message, callId, toolProjectionNeedsDetailHydration);

export { messageContainsToolDetailHydrationCandidate, messageContainsToolMediaHydrationCandidate, toolProjectionNeedsDetailHydration, toolProjectionProvidesHydratedDetails };
