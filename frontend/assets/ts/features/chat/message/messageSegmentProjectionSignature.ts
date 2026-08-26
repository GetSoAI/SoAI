/* SoAI - Chat feature message segment projection signature [frontend/assets/ts/features/chat/message/messageSegmentProjectionSignature.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatHashSignature } from '@core/realtime/streammanager/hashSignature.ts';
import { isArray, isNumber, isString } from '@core/typeGuards.ts';
import type { AssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveToolProjectionActiveStreamingSignature } from '@features/chat/toolactivity/toolProjectionStreamingSignature.ts';

const ACTIVE_STREAM_TEXT_TAIL_SIGNATURE_LENGTH = 128;

const resolveAssistantTimelineProjectionSignature = (message: ChatMessage): string => {
    const timeline = message.assistantEventTimeline;
    if (!isArray(timeline) || timeline.length === 0) {
        return 'timeline:0:0';
    }
    let assistantRevision = 0;
    for (let index = timeline.length - 1; index >= 0; index -= 1) {
        const item = timeline[index];
        if (item && isNumber(item.assistantRevision) && Number.isInteger(item.assistantRevision) && item.assistantRevision > 0) {
            assistantRevision = item.assistantRevision;
            break;
        }
    }
    return `timeline:${String(timeline.length)}:${String(assistantRevision)}:${formatHashSignature(timeline)}`;
};

const timelineIndexMatchesMessage = (message: ChatMessage, timelineIndexState: AssistantTimelineIndexState | null | undefined): timelineIndexState is AssistantTimelineIndexState => {
    const timeline = message.assistantEventTimeline;
    return isArray(timeline) && timelineIndexState !== null && timelineIndexState !== undefined && timelineIndexState.timelineReference === timeline && timelineIndexState.processedLength === timeline.length;
};

const resolveAssistantTimelineIndexProjectionSignature = (timelineIndexState: AssistantTimelineIndexState): string => {
    return `timeline:${String(timelineIndexState.processedLength)}:${String(timelineIndexState.timelineLatestAssistantRevision)}:${timelineIndexState.timelineProjectionHash}`;
};

const resolveProjectionHash = <TValue>(value: TValue): string => {
    if (value === undefined || value === null) {
        return 'none';
    }
    return formatHashSignature(value);
};

const resolveContentProjectionHash = (message: ChatMessage, timelineIndexState: AssistantTimelineIndexState | null | undefined): string => {
    if (timelineIndexMatchesMessage(message, timelineIndexState) && timelineIndexState.hasAssistantTextDeltas && isString(message.content) && message.content === timelineIndexState.assistantVisibleText) {
        const text = timelineIndexState.assistantVisibleText;
        const tail = text.slice(Math.max(0, text.length - ACTIVE_STREAM_TEXT_TAIL_SIGNATURE_LENGTH));
        return ['timeline_text', String(text.length), formatHashSignature(tail), timelineIndexState.timelineProjectionHash].join(':');
    }
    return resolveProjectionHash(message.content);
};

const resolveToolProjectionHash = (message: ChatMessage, timelineIndexState: AssistantTimelineIndexState | null | undefined): string => {
    const projections = message.toolCallProjections;
    if (!timelineIndexMatchesMessage(message, timelineIndexState) || !isArray(projections) || projections.length === 0) {
        return resolveProjectionHash(projections);
    }
    if (!projections.some((projection) => projection.status === 'pending' || projection.status === 'running')) {
        return resolveProjectionHash(projections);
    }
    return formatHashSignature(projections.map((projection) => resolveToolProjectionActiveStreamingSignature(projection)));
};

const resolveTimelineProjectionHash = (message: ChatMessage, timelineIndexState: AssistantTimelineIndexState | null | undefined): string => {
    if (timelineIndexMatchesMessage(message, timelineIndexState)) {
        return resolveAssistantTimelineIndexProjectionSignature(timelineIndexState);
    }
    return resolveAssistantTimelineProjectionSignature(message);
};

const resolveChatMessageSegmentProjectionSignature = (message: ChatMessage, timelineIndexState?: AssistantTimelineIndexState | null): string => {
    return [message.role, String(message.timestamp ?? 0), String(message.assistantTurnAtMs ?? 0), String(message.modelVariantIndex ?? 0), resolveContentProjectionHash(message, timelineIndexState), resolveTimelineProjectionHash(message, timelineIndexState), resolveToolProjectionHash(message, timelineIndexState), resolveProjectionHash(message.inlineToolCollapsedByCallId), resolveProjectionHash(message.inlineThinkingCollapsedByCallId)].join('|');
};

export { resolveChatMessageSegmentProjectionSignature };
