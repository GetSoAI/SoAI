/* SoAI - Worker-safe message segment resolution [frontend/assets/ts/features/chat/message/messageSegmentsResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isNumber } from '@core/typeGuards.ts';
import { createAssistantTimelineIndexState, type AssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import { updateAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexUpdate.ts';
import { resolveAssistantMessageSegmentsFromTimeline } from '@features/chat/message/assistantMessageSegmentResolution.ts';
import { buildMessageContentSegments } from '@features/chat/message/messageSegmentsFromContent.ts';
import { isAssistantMessageRole } from '@features/chat/message/messageRole.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';

const resolveAssistantRevisionFromMessage = (message: ChatMessage): number | null => {
    const timeline = message.assistantEventTimeline;
    if (!isArray(timeline) || timeline.length === 0) {
        return null;
    }
    for (let index = timeline.length - 1; index >= 0; index -= 1) {
        const entry = timeline[index];
        if (!entry) {
            continue;
        }
        if (isNumber(entry.assistantRevision) && Number.isFinite(entry.assistantRevision) && Number.isInteger(entry.assistantRevision) && entry.assistantRevision > 0) {
            return entry.assistantRevision;
        }
    }
    return null;
};

const resolveAssistantMessageRevisionNumberFromMessage = (message: ChatMessage): number => {
    const assistantRevision = resolveAssistantRevisionFromMessage(message);
    return assistantRevision === null ? 0 : assistantRevision;
};

const resolveMessageContentSegmentsForRendering = (message: ChatMessage, dependencies: { cancelledPlaceholderText: string; nowMs: number; timelineIndexState?: AssistantTimelineIndexState | null; timelineIndexAlreadyUpdated?: boolean }): MessageSegment[] => {
    const segments: MessageSegment[] = buildMessageContentSegments(message.content);
    if (!isAssistantMessageRole(message)) {
        return segments;
    }
    const timelineIndexState = dependencies.timelineIndexState ? dependencies.timelineIndexState : createAssistantTimelineIndexState();
    if (dependencies.timelineIndexAlreadyUpdated !== true) {
        updateAssistantTimelineIndexState(timelineIndexState, message);
    }
    return resolveAssistantMessageSegmentsFromTimeline({
        cancelledPlaceholderText: dependencies.cancelledPlaceholderText,
        message,
        baseSegments: segments,
        timelineIndexState
    });
};

export { resolveAssistantMessageRevisionNumberFromMessage, resolveAssistantRevisionFromMessage, resolveMessageContentSegmentsForRendering };
