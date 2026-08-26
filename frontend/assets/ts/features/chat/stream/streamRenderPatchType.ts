/* SoAI - Chat feature stream render patch type [frontend/assets/ts/features/chat/stream/streamRenderPatchType.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isNumber, isString } from '@core/typeGuards.ts';
import { formatHashSignature } from '@core/realtime/streammanager/hashSignature.ts';
import { resolveAssistantTimelineSemanticEventSignature } from '@features/chat/assistanteventtimeline/timelineChronology.ts';
import type { AssistantEventTimelineItem, ChatMessage } from '@features/chat/ChatTypes.ts';
import type { StreamMutationType } from '@features/chat/chatstreamservice/types.ts';
import { resolveStreamMessageTextLength, resolveStreamStatusPreviewCooldownMs, resolveStreamStatusPreviewText, resolveStreamTimelineLength } from '@features/chat/stream/streamActivityVisibleState.ts';
import { resolveToolProjectionActiveStreamingSignature } from '@features/chat/toolactivity/toolProjectionStreamingSignature.ts';

export type StreamRenderPatchType = 'none' | 'passive-state' | 'text-delta' | 'timeline-activity' | 'both' | 'terminal';
export type ActiveStreamRenderPatchType = Exclude<StreamRenderPatchType, 'terminal'>;

export interface StreamRenderSnapshot {
    assistantRevision: number;
    contentLength: number;
    timelineLength: number;
    timelineActivitySignature: string;
    timelineTailEvent: AssistantEventTimelineItem | null;
    statusPreviewText: string;
    statusPreviewCooldownMs: number;
    toolProjectionSignature: string;
}

export interface StreamTextAppend {
    baseAssistantRevision: number;
    baseContentLength: number;
    nextTimelineLength: number;
    textDelta: string;
}

const appendTimelineActivitySignature = (current: string, event: AssistantEventTimelineItem): string => {
    return formatHashSignature(`${current}|${resolveAssistantTimelineSemanticEventSignature(event)}`);
};

const resolveTimelineActivityState = (message: ChatMessage, previous: StreamRenderSnapshot | null): { signature: string; tailEvent: AssistantEventTimelineItem | null } => {
    const timeline = message.assistantEventTimeline;
    if (!isArray(timeline) || timeline.length === 0) return { signature: '', tailEvent: null };
    const previousLength = previous?.timelineLength ?? 0;
    const continuesPreviousTimeline = previous !== null && previousLength <= timeline.length && (previousLength === 0 || timeline[previousLength - 1] === previous.timelineTailEvent);
    let signature = continuesPreviousTimeline ? previous.timelineActivitySignature : '';
    const startIndex = continuesPreviousTimeline ? previousLength : 0;
    for (let index = startIndex; index < timeline.length; index += 1) {
        const event = timeline[index];
        if (event && event.eventType !== 'assistant_text_delta' && event.eventType !== 'completed' && event.eventType !== 'cancelled' && event.eventType !== 'error') {
            signature = appendTimelineActivitySignature(signature, event);
        }
    }
    return { signature, tailEvent: timeline[timeline.length - 1] ?? null };
};

const resolveToolProjectionSignature = (message: ChatMessage): string => {
    const projections = message.toolCallProjections;
    if (!isArray(projections) || projections.length === 0) {
        return '';
    }
    return projections.map((tool) => resolveToolProjectionActiveStreamingSignature(tool)).join('|');
};

const resolveNormalizedRevision = (assistantRevision: number): number => {
    if (!isNumber(assistantRevision) || !Number.isInteger(assistantRevision) || assistantRevision < 0) {
        throw new Error('Stream render snapshot requires a non-negative integer assistant revision');
    }
    return assistantRevision;
};

export const resolveStreamRenderSnapshot = (message: ChatMessage, assistantRevision: number, previous: StreamRenderSnapshot | null): StreamRenderSnapshot => {
    const timelineActivityState = resolveTimelineActivityState(message, previous);
    return {
        assistantRevision: resolveNormalizedRevision(assistantRevision),
        contentLength: resolveStreamMessageTextLength(message),
        timelineLength: resolveStreamTimelineLength(message),
        timelineActivitySignature: timelineActivityState.signature,
        timelineTailEvent: timelineActivityState.tailEvent,
        statusPreviewText: resolveStreamStatusPreviewText(message),
        statusPreviewCooldownMs: resolveStreamStatusPreviewCooldownMs(message),
        toolProjectionSignature: resolveToolProjectionSignature(message)
    };
};

export const resolveStreamRenderPatchType = (inputArguments: { status: 'streaming' | 'complete' | 'error' | 'cancelled'; message: ChatMessage; previous: StreamRenderSnapshot | null; next: StreamRenderSnapshot }): StreamRenderPatchType => {
    if (inputArguments.status !== 'streaming') {
        return 'terminal';
    }

    const previousSnapshot = inputArguments.previous;
    if (previousSnapshot === null) {
        if (inputArguments.next.contentLength > 0 || inputArguments.next.timelineLength > 0) {
            return 'both';
        }
        return 'passive-state';
    }
    const statusPreviewChanged = inputArguments.next.statusPreviewText !== previousSnapshot.statusPreviewText;
    const statusPreviewCooldownChanged = inputArguments.next.statusPreviewCooldownMs !== previousSnapshot.statusPreviewCooldownMs;
    const textChanged = inputArguments.next.contentLength !== previousSnapshot.contentLength;
    const toolProjectionChanged = inputArguments.next.toolProjectionSignature !== previousSnapshot.toolProjectionSignature;
    const firstTextAdded = previousSnapshot.contentLength === 0 && inputArguments.next.contentLength > 0;

    const activityChanged = toolProjectionChanged || inputArguments.next.timelineActivitySignature !== previousSnapshot.timelineActivitySignature;

    if (firstTextAdded) {
        return 'both';
    }
    if (textChanged && activityChanged) {
        return 'both';
    }
    if (activityChanged) {
        return 'timeline-activity';
    }
    if (textChanged) {
        return 'text-delta';
    }
    if (statusPreviewChanged || statusPreviewCooldownChanged) {
        return 'passive-state';
    }
    return 'none';
};

export const resolveStreamTextAppend = (inputArguments: { status: 'streaming' | 'complete' | 'error' | 'cancelled'; mutationType: StreamMutationType; textDelta: string | null; patchType: StreamRenderPatchType; previous: StreamRenderSnapshot | null; next: StreamRenderSnapshot }): StreamTextAppend | null => {
    const previous = inputArguments.previous;
    const textDelta = inputArguments.textDelta;
    if (inputArguments.status !== 'streaming' || inputArguments.mutationType !== 'text-delta' || inputArguments.patchType !== 'text-delta' || previous === null || !isString(textDelta) || textDelta.length === 0) {
        return null;
    }
    if (inputArguments.next.assistantRevision <= previous.assistantRevision || inputArguments.next.contentLength - previous.contentLength !== textDelta.length) {
        return null;
    }
    return {
        baseAssistantRevision: previous.assistantRevision,
        baseContentLength: previous.contentLength,
        nextTimelineLength: inputArguments.next.timelineLength,
        textDelta
    };
};
