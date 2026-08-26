/* SoAI - Chat feature assistant message segment resolution [frontend/assets/ts/features/chat/message/assistantMessageSegmentResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAssistantTimelineRenderEntries } from '@features/chat/assistanteventtimeline/timelineRenderEntries.ts';
import type { AssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import { resolveAnchoredAssistantSegments } from '@features/chat/message/anchoredAssistantSegments.ts';
import { isCancelledAssistantMessage } from '@features/chat/message/placeholderAssistantMessage.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';

const ensureCancelledPlaceholder = (cancelledPlaceholderText: string, message: ChatMessage, segments: MessageSegment[]): MessageSegment[] => {
    if (segments.length > 0) {
        return segments;
    }
    if (!isCancelledAssistantMessage(message)) {
        return segments;
    }
    return [
        {
            type: 'text',
            text: cancelledPlaceholderText,
            value: cancelledPlaceholderText
        }
    ];
};

const shouldRetainAssistantBaseSegment = (segment: MessageSegment, timelineIndexState: AssistantTimelineIndexState): boolean => {
    if (segment.type === 'text') {
        return false;
    }
    if (segment.type === 'image') {
        return !timelineIndexState.hasAssistantImages;
    }
    if (segment.type === 'tool_call') {
        return timelineIndexState.toolRenderSequenceByCallId.size === 0;
    }
    if (segment.type === 'thinking') {
        return timelineIndexState.thinkingBySequenceIndex.size === 0;
    }
    return true;
};

const resolveBaseAssistantText = (segments: MessageSegment[]): string => {
    const textParts: string[] = [];
    for (const segment of segments) {
        if (segment.type === 'text') {
            textParts.push(segment.value);
        }
    }
    return textParts.join('');
};

const resolveBaseAssistantTrailingSegments = (segments: MessageSegment[], timelineIndexState: AssistantTimelineIndexState): MessageSegment[] => {
    const trailingSegments: MessageSegment[] = [];
    for (const segment of segments) {
        if (segment.type === 'text') {
            continue;
        }
        if (shouldRetainAssistantBaseSegment(segment, timelineIndexState)) {
            trailingSegments.push(segment);
        }
    }
    return trailingSegments;
};

const resolveAssistantTextState = (baseSegments: MessageSegment[], timelineIndexState: AssistantTimelineIndexState): { signatureSequence: null; text: string; active: boolean; terminal: boolean } => {
    if (timelineIndexState.hasAssistantTextDeltas) {
        return {
            signatureSequence: null,
            text: timelineIndexState.assistantVisibleText,
            active: timelineIndexState.assistantTextIsStreamingActive,
            terminal: timelineIndexState.hasTerminalEvent
        };
    }
    return {
        signatureSequence: null,
        text: resolveBaseAssistantText(baseSegments),
        active: false,
        terminal: timelineIndexState.hasTerminalEvent
    };
};

const resolveAssistantMessageSegmentsFromTimeline = (inputArguments: { cancelledPlaceholderText: string; message: ChatMessage; baseSegments: MessageSegment[]; timelineIndexState: AssistantTimelineIndexState }): MessageSegment[] => {
    const { message, baseSegments, timelineIndexState } = inputArguments;
    const timelineEntries = resolveAssistantTimelineRenderEntries(message, timelineIndexState);
    if (!timelineIndexState.hasAssistantTextDeltas && timelineEntries.length === 0) {
        return ensureCancelledPlaceholder(inputArguments.cancelledPlaceholderText, message, baseSegments);
    }
    const retainedBaseSegments = timelineIndexState.hasAssistantTextDeltas ? baseSegments.filter((segment) => shouldRetainAssistantBaseSegment(segment, timelineIndexState)) : resolveBaseAssistantTrailingSegments(baseSegments, timelineIndexState);
    const timelineOrderedSegments = resolveAnchoredAssistantSegments(resolveAssistantTextState(baseSegments, timelineIndexState), timelineEntries, retainedBaseSegments);
    return ensureCancelledPlaceholder(inputArguments.cancelledPlaceholderText, message, timelineOrderedSegments);
};

export { resolveAssistantMessageSegmentsFromTimeline };
